# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import hmac
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from plane.db.models.base import BaseModel


def empty_week():
    return {day: [] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


class ImmutableCapacityAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Capacity audit events are immutable.")

    def delete(self):
        raise ValidationError("Capacity audit events are immutable.")


class CapacityAuditEvent(models.Model):
    class Action(models.TextChoices):
        TRAINER_ACTIVATED = "trainer.activated", "Trainer activated"
        TRAINER_SUSPENDED = "trainer.suspended", "Trainer suspended"
        SCHEDULE_UPDATED = "schedule.updated", "Schedule updated"
        GOOGLE_CONNECTED = "google.connected", "Google connected"
        CALENDARS_UPDATED = "google.calendars_updated", "Calendars updated"
        GOOGLE_DISCONNECTED = "google.disconnected", "Google disconnected"
        WORKSHOP_UPDATED = "workshop.updated", "Workshop updated"
        WORKSHOP_REMOVED = "workshop.removed", "Workshop removed"

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workspace_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField(db_index=True)
    trainer_id = models.UUIDField(null=True, blank=True, db_index=True)
    issue_id = models.UUIDField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=64, choices=Action.choices)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableCapacityAuditEventQuerySet.as_manager()

    class Meta:
        db_table = "ext_capacity_audit_events"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["workspace_id", "created_at"], name="ext_cap_audit_ws_time_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Capacity audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Capacity audit events are immutable.")


class TrainerProfile(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="trainer_profiles")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trainer_profiles")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    timezone = models.CharField(max_length=255, default="UTC")
    weekly_schedule = models.JSONField(default=empty_week)
    schedule_revision = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ext_trainer_profiles"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=Q(deleted_at__isnull=True),
                name="ext_trainer_unique_workspace_user",
            )
        ]
        indexes = [models.Index(fields=["workspace", "status"], name="ext_trainer_ws_status_idx")]


class TrainerScheduleException(BaseModel):
    class Mode(models.TextChoices):
        UNAVAILABLE = "unavailable", "Unavailable"
        OVERRIDE = "override", "Override"

    trainer = models.ForeignKey(TrainerProfile, on_delete=models.CASCADE, related_name="schedule_exceptions")
    local_date = models.DateField()
    mode = models.CharField(max_length=16, choices=Mode.choices)
    intervals = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "ext_trainer_schedule_exceptions"
        constraints = [
            models.UniqueConstraint(
                fields=["trainer", "local_date"],
                condition=Q(deleted_at__isnull=True),
                name="ext_trainer_exception_unique_date",
            )
        ]
        indexes = [models.Index(fields=["trainer", "local_date"], name="ext_trainer_exc_date_idx")]


class GoogleCalendarCredential(BaseModel):
    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        REAUTHORIZATION_REQUIRED = "reauthorization_required", "Reauthorization required"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_calendar_credentials"
    )
    google_subject = models.CharField(max_length=255)
    encrypted_refresh_token = models.TextField()
    encryption_key_id = models.CharField(max_length=64)
    granted_scopes = models.JSONField(default=list)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CONNECTED)
    last_successful_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "ext_google_calendar_credentials"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "google_subject"],
                condition=Q(deleted_at__isnull=True),
                name="ext_gcal_credential_unique_subject",
            )
        ]


class TrainerCalendarSelection(BaseModel):
    trainer = models.OneToOneField(TrainerProfile, on_delete=models.CASCADE, related_name="calendar_selection")
    credential = models.ForeignKey(
        GoogleCalendarCredential, on_delete=models.CASCADE, related_name="trainer_selections"
    )
    encrypted_calendar_ids = models.JSONField(default=list)
    calendar_id_hashes = models.JSONField(default=list)
    revision = models.PositiveBigIntegerField(default=1)

    @staticmethod
    def calendar_hash(calendar_id: str) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), calendar_id.encode(), hashlib.sha256).hexdigest()

    class Meta:
        db_table = "ext_trainer_calendar_selections"


class WorkshopSchedule(BaseModel):
    issue = models.OneToOneField("db.Issue", on_delete=models.CASCADE, related_name="workshop_schedule")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_schedules")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="workshop_schedules")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    preparation_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_before_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_after_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )

    class Meta:
        db_table = "ext_workshop_schedules"
        indexes = [
            models.Index(fields=["workspace", "starts_at", "ends_at"], name="ext_workshop_ws_range_idx"),
            models.Index(fields=["project", "starts_at"], name="ext_workshop_proj_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="ext_workshop_valid_range")
        ]

    def save(self, *args, **kwargs):
        self.workspace_id = self.issue.workspace_id
        self.project_id = self.issue.project_id
        super().save(*args, **kwargs)
