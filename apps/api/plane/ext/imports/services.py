# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
import json
import logging
import re
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone

from plane.db.models import Project, ProjectMember, User, WorkspaceMember
from plane.ext.models import (
    ImportAdmissionUsage,
    ImportAuditEvent,
    ImportDispatch,
    ImportJob,
    ImportUserBudget,
    ImportWorkspaceBudget,
)


logger = logging.getLogger(__name__)


ACTIVE_STATUSES = {
    ImportJob.Status.PREPARING,
    ImportJob.Status.QUEUED,
    ImportJob.Status.PROCESSING,
    ImportJob.Status.CANCELLING,
}
TERMINAL_STATUSES = {
    ImportJob.Status.COMPLETED,
    ImportJob.Status.COMPLETED_WITH_ERRORS,
    ImportJob.Status.FAILED,
    ImportJob.Status.CANCELLED,
}
SAFE_AUDIT_METADATA_KEYS = {
    "error_code",
    "publish_attempts",
    "reason",
    "recovered_generation",
    "source_size",
}


class ImportServiceError(Exception):
    code = "import_service_error"


class ImportTransitionError(ImportServiceError):
    code = "invalid_import_transition"


class ImportLeaseLost(ImportServiceError):
    code = "import_lease_lost"


class ImportDispatchUnavailable(ImportServiceError):
    code = "import_dispatch_unavailable"


class ImportCancellationRequested(ImportServiceError):
    code = "import_cancellation_requested"


class ImportAuthorizationRevoked(ImportServiceError):
    code = "import_authorization_revoked"


class ImportProjectUnavailable(ImportServiceError):
    code = "import_project_unavailable"


class ImportDecisionDrift(ImportServiceError):
    code = "import_decision_drift"


class ImportAssigneeIneligible(ImportServiceError):
    code = "import_assignee_ineligible"


class ImportRetryMismatch(ImportServiceError):
    code = "import_retry_mismatch"


class ImportPreviewConsumed(ImportServiceError):
    code = "import_preview_consumed"


class ImportDuplicate(ImportServiceError):
    code = "duplicate_import"


class ImportAlreadyActive(ImportServiceError):
    code = "import_in_progress"


class ImportQuotaExceeded(ImportServiceError):
    code = "import_quota_exceeded"

    def __init__(self, limit: str):
        super().__init__("The Todoist import admission limit was reached.")
        self.limit = limit


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    job: ImportJob
    generation: int
    lease_token: UUID
    task_id: UUID


@dataclass(frozen=True, slots=True)
class DispatchAttempt:
    dispatch_id: UUID
    job_id: UUID
    generation: int
    task_id: UUID


@dataclass(slots=True)
class GuardedMutation:
    job: ImportJob
    project: Project
    actor: User
    _stats: dict[str, Any] | None = None
    _errors: list[dict[str, Any]] | None = None

    def record_progress(self, *, stats: dict[str, Any], errors: list[dict[str, Any]]) -> None:
        self._stats = stats
        self._errors = errors


@dataclass(frozen=True, slots=True)
class LockedBudgets:
    workspace: ImportWorkspaceBudget
    user: ImportUserBudget | None


def _bounded_runtime_setting(name: str, minimum: int, maximum: int) -> int:
    try:
        value = int(getattr(settings, name))
    except (AttributeError, TypeError, ValueError) as error:
        raise ImproperlyConfigured(f"{name} must be an integer") from error
    if value < minimum or value > maximum:
        raise ImproperlyConfigured(f"{name} must be between {minimum} and {maximum}")
    return value


def lease_duration() -> timedelta:
    return timedelta(seconds=_bounded_runtime_setting("TODOIST_IMPORT_LEASE_SECONDS", 30, 900))


def recovery_grace() -> timedelta:
    return timedelta(seconds=_bounded_runtime_setting("TODOIST_IMPORT_RECOVERY_GRACE_SECONDS", 0, 300))


def source_retention() -> timedelta:
    return timedelta(hours=_bounded_runtime_setting("TODOIST_IMPORT_SOURCE_RETENTION_HOURS", 1, 168))


def _create_budget_row(model, **values) -> None:
    try:
        with transaction.atomic():
            model.objects.create(**values)
    except IntegrityError:
        # Another request created the unique budget row. The outer transaction
        # remains usable because the collision was isolated in a savepoint.
        pass


def _lock_budgets(*, workspace_id: UUID, user_id: UUID | None) -> LockedBudgets:
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Import budgets must be locked inside a transaction.")
    if not ImportWorkspaceBudget.objects.filter(workspace_id=workspace_id).exists():
        _create_budget_row(ImportWorkspaceBudget, workspace_id=workspace_id)
    workspace_budget = ImportWorkspaceBudget.objects.select_for_update().get(workspace_id=workspace_id)

    user_budget = None
    if user_id is not None:
        if not ImportUserBudget.objects.filter(workspace_id=workspace_id, user_id=user_id).exists():
            _create_budget_row(
                ImportUserBudget,
                workspace_id=workspace_id,
                user_id=user_id,
            )
        user_budget = ImportUserBudget.objects.select_for_update().get(
            workspace_id=workspace_id,
            user_id=user_id,
        )
    return LockedBudgets(workspace=workspace_budget, user=user_budget)


def _lock_job_and_budgets(job_id: UUID) -> tuple[ImportJob, LockedBudgets]:
    identity = ImportJob.objects.filter(pk=job_id).values("workspace_id", "initiated_by_id").first()
    if identity is None:
        raise ImportJob.DoesNotExist
    budgets = _lock_budgets(
        workspace_id=identity["workspace_id"],
        user_id=identity["initiated_by_id"],
    )
    job = ImportJob.objects.select_for_update().get(pk=job_id)
    return job, budgets


def _release_quota_locked(job: ImportJob, budgets: LockedBudgets, *, now) -> None:
    if job.quota_released_at is not None:
        return
    workspace_budget = budgets.workspace
    workspace_budget.active_jobs = max(0, workspace_budget.active_jobs - 1)
    workspace_budget.active_source_bytes = max(0, workspace_budget.active_source_bytes - job.source_size)
    workspace_budget.save(update_fields=["active_jobs", "active_source_bytes", "updated_at"])
    if budgets.user is not None:
        budgets.user.active_jobs = max(0, budgets.user.active_jobs - 1)
        budgets.user.save(update_fields=["active_jobs", "updated_at"])
    job.quota_released_at = now


@transaction.atomic
def release_quota_once(*, job_id: UUID) -> bool:
    """Release a job's hard admission reservation at most once."""

    job, budgets = _lock_job_and_budgets(job_id)
    if job.quota_released_at is not None:
        return False
    _release_quota_locked(job, budgets, now=timezone.now())
    job.save(update_fields=["quota_released_at", "updated_at"])
    return True


def build_manifest_digest(
    *,
    provider: str,
    workspace_id: UUID,
    project_id: UUID,
    source_digest: str,
    initiated_by_id: UUID,
    config: dict[str, Any],
) -> str:
    manifest = {
        "config": config,
        "initiated_by_id": str(initiated_by_id),
        "project_id": str(project_id),
        "provider": provider,
        "source_digest": source_digest,
        "workspace_id": str(workspace_id),
    }
    canonical = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _job_manifest_matches(job: ImportJob) -> bool:
    if job.initiated_by_id is None or not isinstance(job.config, dict):
        return False
    return job.manifest_digest == build_manifest_digest(
        provider=job.provider,
        workspace_id=job.workspace_id,
        project_id=job.project_id,
        source_digest=job.source_digest,
        initiated_by_id=job.initiated_by_id,
        config=job.config,
    )


def _request_id(value: str | None = None) -> str:
    candidate = value or str(uuid4())
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", candidate) is None:
        return str(uuid4())
    return candidate


def _safe_log_code(value: Any) -> str:
    candidate = str(value or "")
    return candidate if re.fullmatch(r"[A-Za-z0-9_.:-]{0,100}", candidate) else "invalid"


def _log_audit_event(event: ImportAuditEvent) -> None:
    logger.info(
        "todoist_import_event action=%s workspace_id=%s project_id=%s job_id=%s "
        "actor_id=%s generation=%s previous_status=%s resulting_status=%s reason=%s",
        _safe_log_code(event.action),
        event.workspace_id,
        event.project_id,
        event.job_id or "",
        event.actor_id or "",
        event.execution_generation,
        _safe_log_code(event.previous_status),
        _safe_log_code(event.resulting_status),
        _safe_log_code(event.metadata.get("reason", "")),
    )


def _audit(
    *,
    job: ImportJob,
    action: str,
    previous_status: str,
    actor_id: UUID | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    safe_metadata = metadata or {}
    if not set(safe_metadata).issubset(SAFE_AUDIT_METADATA_KEYS):
        raise ValueError("Import audit metadata contains a prohibited field.")
    if any(not isinstance(value, (str, int, bool, type(None))) for value in safe_metadata.values()):
        raise ValueError("Import audit metadata contains a prohibited value.")
    event = ImportAuditEvent.objects.create(
        workspace_id=job.workspace_id,
        project_id=job.project_id,
        job_id=job.id,
        actor_id=actor_id,
        action=action,
        previous_status=previous_status,
        resulting_status=job.status,
        execution_generation=job.execution_generation,
        request_id=_request_id(request_id),
        metadata=safe_metadata,
    )
    transaction.on_commit(lambda: _log_audit_event(event))


def audit_quota_rejection(
    *,
    workspace_id: UUID,
    project_id: UUID,
    actor_id: UUID,
    limit: str,
    request_id: str | None = None,
) -> None:
    """Record a denied admission without creating a misleading ImportJob."""

    event = ImportAuditEvent.objects.create(
        workspace_id=workspace_id,
        project_id=project_id,
        job_id=None,
        actor_id=actor_id,
        action=ImportAuditEvent.Action.QUOTA_REJECTED,
        previous_status="",
        resulting_status="rejected",
        execution_generation=0,
        request_id=_request_id(request_id),
        metadata={"reason": limit},
    )
    transaction.on_commit(lambda: _log_audit_event(event))


@transaction.atomic
def reserve_job(
    *,
    workspace,
    project,
    initiated_by,
    source_digest: str,
    source_size: int,
    config: dict[str, Any],
    stats: dict[str, Any],
    errors: list[dict[str, Any]],
    preview_nonce: UUID | None = None,
    request_id: str | None = None,
    retry_of_id: UUID | None = None,
) -> ImportJob:
    source_rows = stats.get("source_rows", 0) if isinstance(stats, dict) else 0
    if not isinstance(source_rows, int) or source_rows < 0:
        raise ValueError("Import source row count must be a non-negative integer.")
    now = timezone.now()
    preview_nonce = preview_nonce or uuid4()
    budgets = _lock_budgets(workspace_id=workspace.id, user_id=initiated_by.id)
    assert budgets.user is not None
    locked_project = (
        Project.objects.select_for_update()
        .filter(pk=project.id, workspace_id=workspace.id, archived_at__isnull=True)
        .first()
    )
    if locked_project is None:
        raise ImportProjectUnavailable("The destination project is no longer available.")
    if ImportJob.objects.filter(preview_nonce=preview_nonce).exists():
        raise ImportPreviewConsumed("The import preview has already been used.")
    if ImportJob.objects.filter(project=locked_project, status__in=ACTIVE_STATUSES).exists():
        raise ImportAlreadyActive("An import is already active for this project.")
    if (
        config.get("allow_duplicate") is not True
        and ImportJob.objects.filter(
            project=locked_project,
            source_digest=source_digest,
            status__in={ImportJob.Status.COMPLETED, ImportJob.Status.COMPLETED_WITH_ERRORS},
        ).exists()
    ):
        raise ImportDuplicate("This exact source has already been imported into the project.")
    rolling_cutoff = now - timedelta(hours=24)
    workspace_usage = ImportAdmissionUsage.objects.filter(
        workspace_id=workspace.id,
        accepted_at__gt=rolling_cutoff,
    ).aggregate(jobs=Count("id"), rows=Sum("source_rows"))
    user_usage = ImportAdmissionUsage.objects.filter(
        workspace_id=workspace.id,
        user_id=initiated_by.id,
        accepted_at__gt=rolling_cutoff,
    ).aggregate(jobs=Count("id"), rows=Sum("source_rows"))
    workspace_rows = workspace_usage["rows"] or 0

    if budgets.user.active_jobs >= _bounded_runtime_setting("TODOIST_IMPORT_MAX_ACTIVE_PER_USER", 1, 100):
        raise ImportQuotaExceeded("active_user_imports")
    if budgets.workspace.active_jobs >= _bounded_runtime_setting("TODOIST_IMPORT_MAX_ACTIVE_PER_WORKSPACE", 1, 1000):
        raise ImportQuotaExceeded("active_workspace_imports")
    if budgets.workspace.active_source_bytes + source_size > _bounded_runtime_setting(
        "TODOIST_IMPORT_MAX_ACTIVE_SOURCE_BYTES_PER_WORKSPACE",
        1,
        10 * 1024 * 1024 * 1024,
    ):
        raise ImportQuotaExceeded("active_workspace_source_bytes")
    if workspace_rows + source_rows > _bounded_runtime_setting(
        "TODOIST_IMPORT_MAX_ROWS_PER_WORKSPACE_24H",
        1,
        10_000_000,
    ):
        raise ImportQuotaExceeded("workspace_rows_24h")

    manifest_digest = build_manifest_digest(
        provider=ImportJob.Provider.TODOIST_CSV,
        workspace_id=workspace.id,
        project_id=project.id,
        source_digest=source_digest,
        initiated_by_id=initiated_by.id,
        config=config,
    )
    retry_of = None
    idempotency_namespace = uuid4()
    if retry_of_id is not None:
        retry_of = ImportJob.objects.select_for_update().filter(pk=retry_of_id).first()
        if (
            retry_of is None
            or retry_of.status != ImportJob.Status.FAILED
            or retry_of.provider != ImportJob.Provider.TODOIST_CSV
            or retry_of.workspace_id != workspace.id
            or retry_of.project_id != project.id
            or retry_of.initiated_by_id != initiated_by.id
            or retry_of.source_digest != source_digest
            or retry_of.manifest_digest != manifest_digest
        ):
            raise ImportRetryMismatch("The requested retry does not match the failed import decision.")
        idempotency_namespace = retry_of.idempotency_namespace

    budgets.workspace.active_jobs += 1
    budgets.workspace.active_source_bytes += source_size
    budgets.workspace.window_started_at = rolling_cutoff
    budgets.workspace.accepted_jobs = workspace_usage["jobs"] + 1
    budgets.workspace.accepted_rows = workspace_rows + source_rows
    budgets.workspace.save(
        update_fields=[
            "active_jobs",
            "active_source_bytes",
            "window_started_at",
            "accepted_jobs",
            "accepted_rows",
            "updated_at",
        ]
    )
    budgets.user.active_jobs += 1
    budgets.user.window_started_at = rolling_cutoff
    budgets.user.accepted_jobs = user_usage["jobs"] + 1
    budgets.user.accepted_rows = (user_usage["rows"] or 0) + source_rows
    budgets.user.save(
        update_fields=[
            "active_jobs",
            "window_started_at",
            "accepted_jobs",
            "accepted_rows",
            "updated_at",
        ]
    )

    job = ImportJob.objects.create(
        workspace=workspace,
        project=project,
        initiated_by=initiated_by,
        status=ImportJob.Status.PREPARING,
        source_digest=source_digest,
        preview_nonce=preview_nonce,
        source_size=source_size,
        config=config,
        stats=stats,
        errors=errors,
        manifest_digest=manifest_digest,
        idempotency_namespace=idempotency_namespace,
        retry_of=retry_of,
    )
    job.source_key = f"imports/{workspace.id}/{job.id}/source.csv"
    job.save(update_fields=["source_key", "updated_at"])
    ImportAdmissionUsage.objects.create(
        workspace=workspace,
        user=initiated_by,
        job=job,
        source_rows=source_rows,
        accepted_at=now,
    )
    _audit(
        job=job,
        action=ImportAuditEvent.Action.CREATED,
        previous_status="",
        actor_id=initiated_by.id,
        request_id=request_id,
        metadata={"source_size": source_size},
    )
    return job


@transaction.atomic
def fail_preparing_job(*, job_id: UUID, reason: str) -> ImportJob:
    job, budgets = _lock_job_and_budgets(job_id)
    if job.status == ImportJob.Status.CANCELLED:
        return job
    if job.status != ImportJob.Status.PREPARING:
        raise ImportTransitionError("Only a preparing import can fail during source storage.")
    previous_status = job.status
    now = timezone.now()
    job.status = ImportJob.Status.FAILED
    job.reason = reason
    job.config = {}
    job.completed_at = now
    _release_quota_locked(job, budgets, now=now)
    job.save(update_fields=["status", "reason", "config", "completed_at", "quota_released_at", "updated_at"])
    _audit(
        job=job,
        action=ImportAuditEvent.Action.TERMINALIZED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
        metadata={"reason": reason},
    )
    return job


@transaction.atomic
def mark_source_stored(*, job_id: UUID, source_key: str) -> tuple[ImportJob, ImportDispatch]:
    job = ImportJob.objects.select_for_update().get(pk=job_id)
    if job.status != ImportJob.Status.PREPARING:
        raise ImportTransitionError("Only a preparing import can be queued.")
    previous_status = job.status
    now = timezone.now()
    task_id = uuid4()
    job.status = ImportJob.Status.QUEUED
    job.source_key = source_key
    job.queued_at = now
    job.retention_expires_at = now + source_retention()
    job.celery_task_id = str(task_id)
    job.save(
        update_fields=[
            "status",
            "source_key",
            "queued_at",
            "retention_expires_at",
            "celery_task_id",
            "updated_at",
        ]
    )
    dispatch = ImportDispatch.objects.create(
        job=job,
        generation=job.execution_generation,
        task_id=task_id,
    )
    _audit(
        job=job,
        action=ImportAuditEvent.Action.SOURCE_STORED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
        metadata={"source_size": job.source_size},
    )
    return job, dispatch


@transaction.atomic
def prepare_dispatch_attempt(*, dispatch_id: UUID, allow_stale_published: bool = False) -> DispatchAttempt:
    dispatch = ImportDispatch.objects.select_for_update().select_related("job").get(pk=dispatch_id)
    now = timezone.now()
    permitted = dispatch.state == ImportDispatch.State.PENDING or (
        allow_stale_published and dispatch.state == ImportDispatch.State.PUBLISHED
    )
    if not permitted or dispatch.available_at > now or dispatch.publish_attempts >= 100:
        raise ImportDispatchUnavailable("The import dispatch is not publishable.")
    if dispatch.job.status != ImportJob.Status.QUEUED or dispatch.job.execution_generation != dispatch.generation:
        if dispatch.state != ImportDispatch.State.SUPERSEDED:
            dispatch.state = ImportDispatch.State.SUPERSEDED
            dispatch.save(update_fields=["state", "updated_at"])
        raise ImportDispatchUnavailable("The import dispatch generation is no longer active.")
    dispatch.publish_attempts += 1
    dispatch.last_error_code = ""
    dispatch.save(update_fields=["publish_attempts", "last_error_code", "updated_at"])
    _audit(
        job=dispatch.job,
        action=ImportAuditEvent.Action.DISPATCH_ATTEMPTED,
        previous_status=dispatch.job.status,
        actor_id=dispatch.job.initiated_by_id,
        metadata={"publish_attempts": dispatch.publish_attempts},
    )
    return DispatchAttempt(
        dispatch_id=dispatch.id,
        job_id=dispatch.job_id,
        generation=dispatch.generation,
        task_id=dispatch.task_id,
    )


@transaction.atomic
def mark_dispatch_published(*, dispatch_id: UUID) -> None:
    dispatch = ImportDispatch.objects.select_for_update().get(pk=dispatch_id)
    if dispatch.state not in {ImportDispatch.State.PENDING, ImportDispatch.State.PUBLISHED}:
        return
    dispatch.state = ImportDispatch.State.PUBLISHED
    dispatch.published_at = timezone.now()
    dispatch.last_error_code = ""
    dispatch.save(update_fields=["state", "published_at", "last_error_code", "updated_at"])


@transaction.atomic
def mark_dispatch_failed(*, dispatch_id: UUID, error_code: str) -> None:
    if error_code not in ImportDispatch.ErrorCode.values or not error_code:
        raise ValueError("Unknown import dispatch error code.")
    dispatch = ImportDispatch.objects.select_for_update().filter(pk=dispatch_id).first()
    if dispatch is None or dispatch.state in {ImportDispatch.State.CONSUMED, ImportDispatch.State.SUPERSEDED}:
        return
    dispatch.last_error_code = error_code
    dispatch.save(update_fields=["last_error_code", "updated_at"])


@transaction.atomic
def claim_execution(*, job_id: UUID, generation: int, task_id: str | None) -> ExecutionClaim | None:
    if not task_id:
        return None
    try:
        parsed_task_id = UUID(task_id)
    except (TypeError, ValueError):
        return None
    try:
        job, budgets = _lock_job_and_budgets(job_id)
    except ImportJob.DoesNotExist:
        return None
    if job.status != ImportJob.Status.QUEUED or job.execution_generation != generation:
        return None
    dispatch_filter = {
        "job": job,
        "generation": generation,
        "task_id": parsed_task_id,
        "state__in": [ImportDispatch.State.PENDING, ImportDispatch.State.PUBLISHED],
    }
    if not ImportDispatch.objects.filter(**dispatch_filter).exists():
        return None

    failure = _lock_execution_context(job)
    dispatch = ImportDispatch.objects.select_for_update().filter(**dispatch_filter).first()
    if dispatch is None:
        return None
    if failure is not None or not _job_manifest_matches(job):
        previous_status = job.status
        reason = failure or "decision_drift"
        action = (
            ImportAuditEvent.Action.AUTHORIZATION_REVOKED
            if reason == "authorization_revoked"
            else ImportAuditEvent.Action.DECISION_DRIFT
            if reason == "decision_drift"
            else ImportAuditEvent.Action.TERMINALIZED
        )
        now = timezone.now()
        job.status = ImportJob.Status.FAILED
        job.reason = reason
        job.completed_at = now
        job.config = {}
        job.celery_task_id = ""
        _release_quota_locked(job, budgets, now=now)
        job.save()
        dispatch.state = ImportDispatch.State.SUPERSEDED
        dispatch.save(update_fields=["state", "updated_at"])
        _audit(
            job=job,
            action=action,
            previous_status=previous_status,
            actor_id=job.initiated_by_id,
            metadata={"reason": reason},
        )
        return None
    previous_status = job.status
    now = timezone.now()
    token = uuid4()
    job.status = ImportJob.Status.PROCESSING
    job.attempt_count += 1
    job.lease_token = token
    job.lease_expires_at = now + lease_duration()
    job.heartbeat_at = now
    job.started_at = job.started_at or now
    job.celery_task_id = str(parsed_task_id)
    job.reason = ""
    job.save(
        update_fields=[
            "status",
            "attempt_count",
            "lease_token",
            "lease_expires_at",
            "heartbeat_at",
            "started_at",
            "celery_task_id",
            "reason",
            "updated_at",
        ]
    )
    dispatch.state = ImportDispatch.State.CONSUMED
    dispatch.published_at = dispatch.published_at or now
    dispatch.consumed_at = now
    dispatch.save(update_fields=["state", "published_at", "consumed_at", "updated_at"])
    _audit(
        job=job,
        action=ImportAuditEvent.Action.CLAIMED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
    )
    return ExecutionClaim(job=job, generation=generation, lease_token=token, task_id=parsed_task_id)


def _lock_execution_context(job: ImportJob) -> str | None:
    if job.initiated_by_id is None:
        return "authorization_revoked"
    actor = User.objects.select_for_update().filter(pk=job.initiated_by_id, is_active=True).first()
    if actor is None:
        return "authorization_revoked"
    membership = (
        WorkspaceMember.objects.select_for_update()
        .filter(
            workspace_id=job.workspace_id,
            member_id=actor.id,
            is_active=True,
            role__gte=20,
        )
        .first()
    )
    if membership is None:
        return "authorization_revoked"
    project = (
        Project.objects.select_for_update()
        .filter(
            pk=job.project_id,
            workspace_id=job.workspace_id,
            archived_at__isnull=True,
        )
        .first()
    )
    if project is None:
        return "project_unavailable"
    job.initiated_by = actor
    job.project = project
    return None


@contextmanager
def guard_mutation(
    *,
    job_id: UUID,
    generation: int,
    lease_token: UUID,
) -> Iterator[GuardedMutation]:
    """Fence and authorize exactly one importer mutation transaction."""

    with transaction.atomic():
        job = ImportJob.objects.select_for_update().get(pk=job_id)
        _require_owner(job, generation=generation, lease_token=lease_token)
        if job.status == ImportJob.Status.CANCELLING or job.cancel_requested_at is not None:
            raise ImportCancellationRequested("The import was cancelled before the next mutation.")
        if not _job_manifest_matches(job):
            raise ImportDecisionDrift("The stored import decision no longer matches its manifest.")
        failure = _lock_execution_context(job)
        if failure == "authorization_revoked":
            raise ImportAuthorizationRevoked("The initiating administrator is no longer authorized.")
        if failure == "project_unavailable":
            raise ImportProjectUnavailable("The destination project is no longer available.")

        assert job.initiated_by is not None
        now = timezone.now()
        job.heartbeat_at = now
        job.lease_expires_at = now + lease_duration()
        job.save(update_fields=["heartbeat_at", "lease_expires_at", "updated_at"])
        guarded = GuardedMutation(job=job, project=job.project, actor=job.initiated_by)
        yield guarded
        if guarded._stats is not None and guarded._errors is not None:
            job.stats = guarded._stats
            job.errors = guarded._errors
            job.save(update_fields=["stats", "errors", "updated_at"])


def lock_eligible_assignee(*, project_id: UUID, assignee_id: UUID) -> User:
    """Validate and lock a mapped assignee inside a guarded mutation."""

    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Assignee eligibility must be checked inside a mutation transaction.")
    assignee = User.objects.select_for_update().filter(pk=assignee_id, is_active=True).first()
    if assignee is None:
        raise ImportAssigneeIneligible("The mapped assignee account is inactive.")
    membership = (
        ProjectMember.objects.select_for_update()
        .filter(
            project_id=project_id,
            member_id=assignee_id,
            is_active=True,
            role__gte=15,
        )
        .first()
    )
    if membership is None:
        raise ImportAssigneeIneligible("The mapped assignee is no longer an active project member.")
    return assignee


def _require_owner(job: ImportJob, *, generation: int, lease_token: UUID) -> None:
    if (
        job.execution_generation != generation
        or job.lease_token != lease_token
        or job.status not in {ImportJob.Status.PROCESSING, ImportJob.Status.CANCELLING}
        or job.lease_expires_at is None
        or job.lease_expires_at <= timezone.now()
    ):
        raise ImportLeaseLost("The import execution lease is no longer valid.")


@transaction.atomic
def finish_execution(
    *,
    job_id: UUID,
    generation: int,
    lease_token: UUID,
    status: str,
    reason: str = "",
    errors: list[dict[str, Any]] | None = None,
    stats: dict[str, Any] | None = None,
) -> ImportJob:
    if status not in TERMINAL_STATUSES:
        raise ValueError("Import execution can only finish in a terminal state.")
    job, budgets = _lock_job_and_budgets(job_id)
    _require_owner(job, generation=generation, lease_token=lease_token)
    previous_status = job.status
    if job.status == ImportJob.Status.CANCELLING or job.cancel_requested_at is not None:
        status = ImportJob.Status.CANCELLED
        reason = "cancelled_by_user"
    now = timezone.now()
    job.status = status
    job.reason = reason
    job.completed_at = now
    job.heartbeat_at = now
    job.config = {}
    job.lease_token = None
    job.lease_expires_at = None
    job.celery_task_id = ""
    _release_quota_locked(job, budgets, now=now)
    if errors is not None:
        job.errors = errors
    if stats is not None:
        job.stats = stats
    job.save()
    audit_action = (
        ImportAuditEvent.Action.AUTHORIZATION_REVOKED
        if reason == "authorization_revoked"
        else ImportAuditEvent.Action.DECISION_DRIFT
        if reason == "decision_drift"
        else ImportAuditEvent.Action.TERMINALIZED
    )
    _audit(
        job=job,
        action=audit_action,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
        metadata={"reason": reason},
    )
    return job


@transaction.atomic
def schedule_retry(
    *,
    job_id: UUID,
    generation: int,
    lease_token: UUID,
    delay: timedelta,
) -> ImportDispatch:
    job = ImportJob.objects.select_for_update().get(pk=job_id)
    _require_owner(job, generation=generation, lease_token=lease_token)
    if job.status == ImportJob.Status.CANCELLING or job.cancel_requested_at is not None:
        raise ImportTransitionError("A cancelling import cannot be retried.")
    previous_status = job.status
    job.execution_generation += 1
    task_id = uuid4()
    job.status = ImportJob.Status.QUEUED
    job.reason = "retrying"
    job.lease_token = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.celery_task_id = str(task_id)
    job.save(
        update_fields=[
            "execution_generation",
            "status",
            "reason",
            "lease_token",
            "lease_expires_at",
            "heartbeat_at",
            "celery_task_id",
            "updated_at",
        ]
    )
    dispatch = ImportDispatch.objects.create(
        job=job,
        generation=job.execution_generation,
        task_id=task_id,
        available_at=timezone.now() + delay,
    )
    _audit(
        job=job,
        action=ImportAuditEvent.Action.RETRY_SCHEDULED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
    )
    return dispatch


@transaction.atomic
def recover_expired_execution(*, job_id: UUID) -> ImportDispatch | None:
    job = ImportJob.objects.select_for_update().filter(pk=job_id).first()
    now = timezone.now()
    if (
        job is None
        or job.status != ImportJob.Status.PROCESSING
        or job.lease_expires_at is None
        or job.lease_expires_at + recovery_grace() > now
    ):
        return None
    previous_status = job.status
    recovered_generation = job.execution_generation
    job.execution_generation += 1
    task_id = uuid4()
    job.status = ImportJob.Status.QUEUED
    job.reason = "lease_recovered"
    job.lease_token = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.celery_task_id = str(task_id)
    job.save(
        update_fields=[
            "execution_generation",
            "status",
            "reason",
            "lease_token",
            "lease_expires_at",
            "heartbeat_at",
            "celery_task_id",
            "updated_at",
        ]
    )
    dispatch = ImportDispatch.objects.create(job=job, generation=job.execution_generation, task_id=task_id)
    _audit(
        job=job,
        action=ImportAuditEvent.Action.LEASE_RECOVERED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
        metadata={"recovered_generation": recovered_generation},
    )
    return dispatch


@transaction.atomic
def request_cancellation(*, job_id: UUID, actor_id: UUID, request_id: str | None = None) -> tuple[ImportJob, bool]:
    job, budgets = _lock_job_and_budgets(job_id)
    if job.status not in ACTIVE_STATUSES:
        raise ImportTransitionError("Only an active import can be cancelled.")
    previous_status = job.status
    now = timezone.now()
    job.cancel_requested_at = job.cancel_requested_at or now
    terminal = job.status in {ImportJob.Status.PREPARING, ImportJob.Status.QUEUED}
    if terminal:
        job.status = ImportJob.Status.CANCELLED
        job.reason = "cancelled_by_user"
        job.completed_at = now
        job.config = {}
        job.celery_task_id = ""
        _release_quota_locked(job, budgets, now=now)
        ImportDispatch.objects.filter(
            job=job,
            state__in=[ImportDispatch.State.PENDING, ImportDispatch.State.PUBLISHED],
        ).update(state=ImportDispatch.State.SUPERSEDED)
    else:
        job.status = ImportJob.Status.CANCELLING
    job.save()
    _audit(
        job=job,
        action=ImportAuditEvent.Action.CANCELLATION_REQUESTED,
        previous_status=previous_status,
        actor_id=actor_id,
        request_id=request_id,
    )
    return job, terminal


@transaction.atomic
def expire_source(*, job_id: UUID) -> ImportJob | None:
    try:
        job, budgets = _lock_job_and_budgets(job_id)
    except ImportJob.DoesNotExist:
        return None
    if job.status in TERMINAL_STATUSES:
        return job
    now = timezone.now()
    if (
        job.status in {ImportJob.Status.PROCESSING, ImportJob.Status.CANCELLING}
        and job.lease_expires_at is not None
        and job.lease_expires_at + recovery_grace() > now
    ):
        return None
    previous_status = job.status
    cancelled = job.cancel_requested_at is not None or job.status == ImportJob.Status.CANCELLING
    job.status = ImportJob.Status.CANCELLED if cancelled else ImportJob.Status.FAILED
    job.reason = "cancelled_by_user" if cancelled else "source_expired"
    job.completed_at = now
    job.config = {}
    job.lease_token = None
    job.lease_expires_at = None
    job.celery_task_id = ""
    _release_quota_locked(job, budgets, now=now)
    job.save()
    ImportDispatch.objects.filter(
        job=job,
        state__in=[ImportDispatch.State.PENDING, ImportDispatch.State.PUBLISHED],
    ).update(state=ImportDispatch.State.SUPERSEDED)
    _audit(
        job=job,
        action=ImportAuditEvent.Action.TERMINALIZED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
        metadata={"reason": job.reason},
    )
    return job


@transaction.atomic
def mark_source_deleted(*, job_id: UUID) -> ImportJob:
    job = ImportJob.objects.select_for_update().get(pk=job_id)
    if job.status not in TERMINAL_STATUSES:
        raise ImportTransitionError("An active import source cannot be deleted.")
    previous_status = job.status
    job.source_key = ""
    job.source_deleted_at = timezone.now()
    job.save(update_fields=["source_key", "source_deleted_at", "updated_at"])
    _audit(
        job=job,
        action=ImportAuditEvent.Action.SOURCE_DELETED,
        previous_status=previous_status,
        actor_id=job.initiated_by_id,
    )
    return job
