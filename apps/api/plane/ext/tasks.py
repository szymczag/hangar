# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
import logging

# Django imports
from django.db.models import Q
from django.utils import timezone

# Third party imports
from celery import shared_task

# Module imports
from plane.ext.importers import execute_todoist_import
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


@shared_task
def run_todoist_import(job_id: str) -> None:
    now = timezone.now()
    claimed = ImportJob.objects.filter(pk=job_id, status=ImportJob.Status.QUEUED).update(
        status=ImportJob.Status.PROCESSING,
        started_at=now,
    )
    if not claimed:
        return

    job = ImportJob.objects.select_related("project", "workspace", "initiated_by").get(pk=job_id)
    if job.initiated_by_id is None:
        ImportJob.objects.filter(pk=job.id).update(
            status=ImportJob.Status.FAILED,
            reason="initiator_missing",
            completed_at=timezone.now(),
            config={},
        )
        _delete_job_source(job)
        return

    try:
        stats, diagnostics = execute_todoist_import(job)
        ImportJob.objects.filter(pk=job.id).update(
            status=ImportJob.Status.COMPLETED,
            stats=stats,
            errors=diagnostics,
            reason="",
            completed_at=timezone.now(),
            config={},
        )
    except TodoistImportParseError as exc:
        ImportJob.objects.filter(pk=job.id).update(
            status=ImportJob.Status.FAILED,
            errors=[exc.diagnostic.as_dict()],
            reason=exc.diagnostic.code,
            completed_at=timezone.now(),
            config={},
        )
    except Exception as exc:  # noqa: BLE001 - job failure is converted to a safe status
        logger.error("Todoist import job %s failed with %s", job.id, type(exc).__name__)
        ImportJob.objects.filter(pk=job.id).update(
            status=ImportJob.Status.FAILED,
            reason="import_failed",
            completed_at=timezone.now(),
            config={},
        )
    finally:
        _delete_job_source(job)


@shared_task
def cleanup_import_sources() -> None:
    cutoff = timezone.now() - timedelta(hours=24)
    terminal_statuses = [
        ImportJob.Status.COMPLETED,
        ImportJob.Status.FAILED,
        ImportJob.Status.CANCELLED,
    ]
    jobs = ImportJob.objects.filter(source_key__gt="").filter(
        Q(status__in=terminal_statuses) | Q(created_at__lt=cutoff)
    )
    for job in jobs.iterator(chunk_size=100):
        if job.status not in terminal_statuses:
            ImportJob.objects.filter(pk=job.id).update(
                status=ImportJob.Status.FAILED,
                reason="source_expired",
                completed_at=timezone.now(),
                config={},
            )
        _delete_job_source(job)
