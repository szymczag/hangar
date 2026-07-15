# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from datetime import timedelta
import logging

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from plane.ext.importers import execute_todoist_import
from plane.ext.importers.todoist import ImportCancelled, ImportRowFailure
from plane.ext.imports import todoist_imports_enabled
from plane.ext.models import ImportJob
from plane.ext.utils.import_storage import delete_import_source
from plane.ext.utils.importers.todoist_csv import TodoistImportParseError


logger = logging.getLogger(__name__)


def _delete_job_source(job: ImportJob) -> bool:
    if not job.source_key:
        return True
    if not delete_import_source(job.source_key):
        return False
    ImportJob.objects.filter(pk=job.id).update(source_key="", source_deleted_at=timezone.now())
    job.source_key = ""
    return True


def _claim_job(job_id: str, task_id: str | None, *, redelivered: bool = False) -> ImportJob | None:
    with transaction.atomic():
        job = ImportJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None:
            return None
        if job.celery_task_id and job.celery_task_id != task_id:
            return None
        can_recover_worker_loss = (
            redelivered
            and job.status == ImportJob.Status.PROCESSING
            and bool(job.celery_task_id)
            and job.celery_task_id == task_id
        )
        if job.status != ImportJob.Status.QUEUED and not can_recover_worker_loss:
            return None

        now = timezone.now()
        job.status = ImportJob.Status.PROCESSING
        job.attempt_count += 1
        job.heartbeat_at = now
        job.started_at = job.started_at or now
        job.reason = ""
        job.save(
            update_fields=[
                "status",
                "attempt_count",
                "heartbeat_at",
                "started_at",
                "reason",
                "updated_at",
            ]
        )
    return ImportJob.objects.select_related("project", "workspace", "initiated_by").get(pk=job_id)


def _finish_job(job: ImportJob, *, status: str, reason: str = "", errors=None, stats=None) -> None:
    updates = {
        "status": status,
        "reason": reason,
        "completed_at": timezone.now(),
        "heartbeat_at": timezone.now(),
        "config": {},
    }
    if errors is not None:
        updates["errors"] = errors
    if stats is not None:
        updates["stats"] = stats
    ImportJob.objects.filter(pk=job.id).update(**updates)
    _delete_job_source(job)


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=3)
def run_todoist_import(self, job_id: str) -> None:
    if not todoist_imports_enabled():
        logger.warning("Todoist import task ignored because the importer is disabled")
        return

    delivery_info = self.request.delivery_info or {}
    job = _claim_job(
        job_id,
        self.request.id,
        redelivered=bool(delivery_info.get("redelivered")),
    )
    if job is None:
        return

    if job.initiated_by_id is None:
        _finish_job(job, status=ImportJob.Status.FAILED, reason="initiator_missing")
        return

    try:
        stats, diagnostics = execute_todoist_import(job)
    except ImportCancelled:
        _finish_job(job, status=ImportJob.Status.CANCELLED, reason="cancelled_by_user")
        return
    except TodoistImportParseError as exc:
        _finish_job(
            job,
            status=ImportJob.Status.FAILED,
            reason=exc.diagnostic.code,
            errors=[exc.diagnostic.as_dict()],
        )
        return
    except ImportRowFailure as exc:
        _finish_job(
            job,
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
    except Exception as exc:  # noqa: BLE001 - unexpected failures are retried without exposing values
        logger.error("Todoist import job %s attempt failed with %s", job.id, type(exc).__name__)
        if self.request.retries < self.max_retries:
            ImportJob.objects.filter(pk=job.id, status=ImportJob.Status.PROCESSING).update(
                status=ImportJob.Status.QUEUED,
                heartbeat_at=None,
                reason="retrying",
            )
            raise self.retry(exc=exc, countdown=min(60, 2 ** (self.request.retries + 1)))
        _finish_job(job, status=ImportJob.Status.FAILED, reason="import_failed")
        return

    result_status = ImportJob.Status.COMPLETED_WITH_ERRORS if stats.get("failed", 0) else ImportJob.Status.COMPLETED
    _finish_job(job, status=result_status, stats=stats, errors=diagnostics)


@shared_task
def cleanup_import_sources() -> None:
    cutoff = timezone.now() - timedelta(hours=24)
    terminal_statuses = [
        ImportJob.Status.COMPLETED,
        ImportJob.Status.COMPLETED_WITH_ERRORS,
        ImportJob.Status.FAILED,
        ImportJob.Status.CANCELLED,
    ]
    jobs = ImportJob.objects.filter(source_key__gt="").filter(
        Q(status__in=terminal_statuses) | Q(created_at__lt=cutoff)
    )
    for job in jobs.iterator(chunk_size=100):
        if job.status not in terminal_statuses:
            requested_cancel = job.cancel_requested_at is not None
            ImportJob.objects.filter(pk=job.id).update(
                status=ImportJob.Status.CANCELLED if requested_cancel else ImportJob.Status.FAILED,
                reason="cancelled_by_user" if requested_cancel else "source_expired",
                completed_at=timezone.now(),
                config={},
            )
        _delete_job_source(job)
