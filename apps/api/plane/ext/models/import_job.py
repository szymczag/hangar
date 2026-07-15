# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

# Django imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

# Module imports
from plane.db.models.base import BaseModel


class ImportJob(BaseModel):
    class Provider(models.TextChoices):
        TODOIST_CSV = "todoist_csv", "Todoist CSV"

    class Status(models.TextChoices):
        PREPARING = "preparing", "Preparing"
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        CANCELLING = "cancelling", "Cancelling"
        COMPLETED = "completed", "Completed"
        COMPLETED_WITH_ERRORS = "completed_with_errors", "Completed with errors"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    workspace = models.ForeignKey("db.WorkSpace", on_delete=models.CASCADE, related_name="ext_import_jobs")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="ext_import_jobs")
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ext_import_jobs",
    )
    provider = models.CharField(max_length=32, choices=Provider.choices, default=Provider.TODOIST_CSV)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PREPARING)
    source_key = models.TextField(blank=True)
    source_digest = models.CharField(max_length=64)
    source_size = models.PositiveBigIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    reason = models.CharField(max_length=100, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    execution_generation = models.PositiveBigIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    queued_at = models.DateTimeField(null=True, blank=True)
    retention_expires_at = models.DateTimeField(null=True, blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    source_deleted_at = models.DateTimeField(null=True, blank=True)
    idempotency_namespace = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    manifest_digest = models.CharField(max_length=64)
    retry_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="retry_jobs",
    )
    quota_released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Import Job"
        verbose_name_plural = "Import Jobs"
        db_table = "ext_import_jobs"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "created_at"], name="ext_imp_ws_created_idx"),
            models.Index(fields=["workspace", "status"], name="ext_imp_ws_status_idx"),
            models.Index(fields=["project", "source_digest"], name="ext_imp_project_hash_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=Q(status__in=["preparing", "queued", "processing", "cancelling"]),
                name="ext_imp_one_active_per_project",
            ),
            models.CheckConstraint(
                check=Q(
                    status__in=[
                        "preparing",
                        "queued",
                        "processing",
                        "cancelling",
                        "completed",
                        "completed_with_errors",
                        "failed",
                        "cancelled",
                    ]
                ),
                name="ext_imp_valid_status",
            ),
            models.CheckConstraint(
                check=Q(source_digest__regex=r"^[0-9a-f]{64}$"),
                name="ext_imp_source_digest_sha256",
            ),
            models.CheckConstraint(
                check=Q(manifest_digest__regex=r"^[0-9a-f]{64}$"),
                name="ext_imp_manifest_digest_sha256",
            ),
            models.CheckConstraint(
                check=(
                    ~Q(status="processing")
                    | Q(
                        lease_token__isnull=False,
                        lease_expires_at__isnull=False,
                        started_at__isnull=False,
                    )
                    & ~Q(celery_task_id="")
                ),
                name="ext_imp_processing_has_lease",
            ),
            models.CheckConstraint(
                check=(
                    ~Q(status__in=["completed", "completed_with_errors", "failed", "cancelled"])
                    | Q(
                        completed_at__isnull=False,
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                    )
                ),
                name="ext_imp_terminal_is_fenced",
            ),
            models.CheckConstraint(
                check=(
                    Q(queued_at__isnull=True)
                    | Q(retention_expires_at__isnull=True)
                    | Q(retention_expires_at__gte=models.F("queued_at"))
                ),
                name="ext_imp_valid_retention",
            ),
        ]

    def __str__(self):
        return f"{self.provider} {self.project_id} {self.status}"


class ImportDispatch(BaseModel):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        CONSUMED = "consumed", "Consumed"
        SUPERSEDED = "superseded", "Superseded"

    class ErrorCode(models.TextChoices):
        NONE = "", "None"
        BROKER_UNAVAILABLE = "broker_unavailable", "Broker unavailable"
        PUBLISH_CONFIRMATION_UNKNOWN = "publish_confirmation_unknown", "Publish confirmation unknown"

    job = models.ForeignKey(ImportJob, on_delete=models.PROTECT, related_name="dispatches")
    generation = models.PositiveBigIntegerField()
    task_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    available_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    publish_attempts = models.PositiveSmallIntegerField(default=0)
    last_error_code = models.CharField(max_length=40, choices=ErrorCode.choices, blank=True, default="")

    class Meta:
        db_table = "ext_import_dispatches"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(fields=["job", "generation"], name="ext_imp_dispatch_job_generation"),
            models.CheckConstraint(
                check=Q(state__in=["pending", "published", "consumed", "superseded"]),
                name="ext_imp_dispatch_valid_state",
            ),
            models.CheckConstraint(check=Q(publish_attempts__lte=100), name="ext_imp_dispatch_attempt_limit"),
            models.CheckConstraint(
                check=(
                    Q(state="pending", published_at__isnull=True, consumed_at__isnull=True)
                    | Q(state="published", published_at__isnull=False, consumed_at__isnull=True)
                    | Q(state="consumed", published_at__isnull=False, consumed_at__isnull=False)
                    | Q(state="superseded", consumed_at__isnull=True)
                ),
                name="ext_imp_dispatch_state_times",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "available_at"], name="ext_imp_dispatch_ready_idx"),
        ]


class ImmutableImportAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Import audit events are immutable.")

    def delete(self):
        raise ValidationError("Import audit events are immutable.")


class ImportAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "import.created", "Created"
        SOURCE_STORED = "import.source_stored", "Source stored"
        DISPATCH_ATTEMPTED = "import.dispatch_attempted", "Dispatch attempted"
        CLAIMED = "import.claimed", "Claimed"
        LEASE_RECOVERED = "import.lease_recovered", "Lease recovered"
        RETRY_SCHEDULED = "import.retry_scheduled", "Retry scheduled"
        CANCELLATION_REQUESTED = "import.cancellation_requested", "Cancellation requested"
        AUTHORIZATION_REVOKED = "import.authorization_revoked", "Authorization revoked"
        DECISION_DRIFT = "import.decision_drift", "Decision drift"
        QUOTA_REJECTED = "import.quota_rejected", "Quota rejected"
        TERMINALIZED = "import.terminalized", "Terminalized"
        SOURCE_DELETED = "import.source_deleted", "Source deleted"
        CLEANUP_FAILED = "import.cleanup_failed", "Cleanup failed"

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workspace_id = models.UUIDField(db_index=True)
    project_id = models.UUIDField(db_index=True)
    job_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=64, choices=Action.choices)
    previous_status = models.CharField(max_length=32, blank=True)
    resulting_status = models.CharField(max_length=32)
    execution_generation = models.PositiveBigIntegerField(default=0)
    request_id = models.CharField(max_length=128)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableImportAuditEventQuerySet.as_manager()

    class Meta:
        db_table = "ext_import_audit_events"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                check=Q(
                    action__in=[
                        "import.created",
                        "import.source_stored",
                        "import.dispatch_attempted",
                        "import.claimed",
                        "import.lease_recovered",
                        "import.retry_scheduled",
                        "import.cancellation_requested",
                        "import.authorization_revoked",
                        "import.decision_drift",
                        "import.quota_rejected",
                        "import.terminalized",
                        "import.source_deleted",
                        "import.cleanup_failed",
                    ]
                ),
                name="ext_imp_audit_valid_action",
            ),
            models.CheckConstraint(
                check=Q(request_id__regex=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"),
                name="ext_imp_audit_request_id",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace_id", "created_at"], name="ext_imp_audit_ws_time_idx"),
            models.Index(fields=["action", "created_at"], name="ext_imp_audit_action_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Import audit events are immutable.")
        if not isinstance(self.metadata, dict):
            raise ValidationError("Import audit metadata must be an object.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Import audit events are immutable.")
