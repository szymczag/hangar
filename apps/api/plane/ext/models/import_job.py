# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.db import models
from django.db.models import Q

# Module imports
from plane.db.models.base import BaseModel


class ImportJob(BaseModel):
    class Provider(models.TextChoices):
        TODOIST_CSV = "todoist_csv", "Todoist CSV"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
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
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    source_key = models.TextField(blank=True)
    source_digest = models.CharField(max_length=64)
    source_size = models.PositiveBigIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    reason = models.CharField(max_length=100, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    source_deleted_at = models.DateTimeField(null=True, blank=True)

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
                condition=Q(status__in=["queued", "processing"]),
                name="ext_imp_one_active_per_project",
            )
        ]

    def __str__(self):
        return f"{self.provider} {self.project_id} {self.status}"
