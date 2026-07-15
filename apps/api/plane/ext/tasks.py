# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from datetime import timedelta
import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from plane.ext.importers import execute_todoist_import
from plane.ext.importers.todoist import ImportCancelled, ImportRowFailure
from plane.ext.imports import ImportLeaseLost, ImportTransitionError, todoist_imports_enabled
from plane.ext.imports.dispatcher import publish_import_dispatch
from plane.ext.imports.services import (
    claim_execution,
    expire_source,
    finish_execution,
    mark_source_deleted,
    recover_expired_execution,
    recovery_grace,
    schedule_retry,
)
from plane.ext.models import ImportDispatch, ImportJob
from plane.ext.utils.import_storage import delete_import_source
from plane.ext.utils.importers.todoist_csv import TodoistImportParseError


logger = logging.getLogger(__name__)
MAX_EXECUTION_ATTEMPTS = 4


def _delete_job_source(job: ImportJob) -> bool:
    if not job.source_key:
        return True
    if not delete_import_source(job.source_key):
        return False
    mark_source_deleted(job_id=job.id)
    job.source_key = ""
    return True


def _finish_claim(claim, *, status: str, reason: str = "", errors=None, stats=None) -> ImportJob | None:
    try:
        job = finish_execution(
            job_id=claim.job.id,
            generation=claim.generation,
            lease_token=claim.lease_token,
            status=status,
            reason=reason,
            errors=errors,
            stats=stats,
        )
    except ImportLeaseLost:
        logger.warning("Todoist import execution lost its lease before terminalization")
        return None
    _delete_job_source(job)
    return job


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True)
def run_todoist_import(self, job_id: str, generation: int = 0) -> None:
    if not todoist_imports_enabled():
        logger.warning("Todoist import task ignored because the importer is disabled")
        return

    claim = claim_execution(
        job_id=job_id,
        generation=generation,
        task_id=self.request.id,
    )
    if claim is None:
        return
    job = claim.job

    if job.initiated_by_id is None:
        _finish_claim(claim, status=ImportJob.Status.FAILED, reason="initiator_missing")
        return

    try:
        stats, diagnostics = execute_todoist_import(job)
    except ImportCancelled:
        _finish_claim(claim, status=ImportJob.Status.CANCELLED, reason="cancelled_by_user")
        return
    except TodoistImportParseError as exc:
        _finish_claim(
            claim,
            status=ImportJob.Status.FAILED,
            reason=exc.diagnostic.code,
            errors=[exc.diagnostic.as_dict()],
        )
        return
    except ImportRowFailure as exc:
        _finish_claim(
            claim,
            status=ImportJob.Status.FAILED,
            reason=exc.code,
            errors=[
                {
                    "level": "error",
                    "code": exc.code,
                    "message": "The import source could not be processed.",
                    "row": None,
                    "field": exc.field,
                }
            ],
        )
        return
    except Exception as exc:  # noqa: BLE001 - values are never copied into logs or persisted state
        logger.error("Todoist import execution failed with %s", type(exc).__name__)
        if job.attempt_count < MAX_EXECUTION_ATTEMPTS:
            try:
                schedule_retry(
                    job_id=job.id,
                    generation=claim.generation,
                    lease_token=claim.lease_token,
                    delay=timedelta(seconds=min(60, 2**job.attempt_count)),
                )
            except (ImportLeaseLost, ImportTransitionError):
                return
            return
        _finish_claim(claim, status=ImportJob.Status.FAILED, reason="import_failed")
        return

    result_status = ImportJob.Status.COMPLETED_WITH_ERRORS if stats.get("failed", 0) else ImportJob.Status.COMPLETED
    _finish_claim(claim, status=result_status, stats=stats, errors=diagnostics)


@shared_task
def dispatch_pending_imports() -> None:
    now = timezone.now()
    stale_before = now - timedelta(minutes=5)
    dispatches = (
        ImportDispatch.objects.filter(
            Q(state=ImportDispatch.State.PENDING, available_at__lte=now)
            | Q(state=ImportDispatch.State.PUBLISHED, published_at__lte=stale_before)
        )
        .order_by("available_at")
        .values_list("id", "state")[:100]
    )
    for dispatch_id, state in dispatches:
        publish_import_dispatch(
            dispatch_id,
            allow_stale_published=state == ImportDispatch.State.PUBLISHED,
        )


@shared_task
def recover_expired_import_leases() -> None:
    cutoff = timezone.now() - recovery_grace()
    job_ids = list(
        ImportJob.objects.filter(
            status=ImportJob.Status.PROCESSING,
            lease_expires_at__lte=cutoff,
        )
        .order_by("lease_expires_at")
        .values_list("id", flat=True)[:100]
    )
    for job_id in job_ids:
        dispatch = recover_expired_execution(job_id=job_id)
        if dispatch is not None:
            publish_import_dispatch(dispatch.id)


@shared_task
def cleanup_import_sources() -> None:
    now = timezone.now()
    legacy_cutoff = now - timedelta(hours=24)
    candidate_ids = list(
        ImportJob.objects.filter(source_key__gt="")
        .filter(
            Q(status__in=[
                ImportJob.Status.COMPLETED,
                ImportJob.Status.COMPLETED_WITH_ERRORS,
                ImportJob.Status.FAILED,
                ImportJob.Status.CANCELLED,
            ])
            | Q(retention_expires_at__lte=now)
            | Q(retention_expires_at__isnull=True, created_at__lt=legacy_cutoff)
        )
        .order_by("created_at")
        .values_list("id", flat=True)[:100]
    )
    for job_id in candidate_ids:
        job = expire_source(job_id=job_id)
        if job is not None and job.status in {
            ImportJob.Status.COMPLETED,
            ImportJob.Status.COMPLETED_WITH_ERRORS,
            ImportJob.Status.FAILED,
            ImportJob.Status.CANCELLED,
        }:
            _delete_job_source(job)
