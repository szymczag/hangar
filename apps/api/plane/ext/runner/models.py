# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from plane.db.models.base import BaseModel

from .constants import RunnerInstallationState


class ImmutableAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Runner audit events are immutable.")

    def delete(self):
        raise ValidationError("Runner audit events are immutable.")


class RunnerInstallation(BaseModel):
    class State(models.TextChoices):
        INACTIVE = RunnerInstallationState.INACTIVE, "Inactive"
        ACTIVE = RunnerInstallationState.ACTIVE, "Active"
        SUSPENDED = RunnerInstallationState.SUSPENDED, "Suspended"
        REVOKED = RunnerInstallationState.REVOKED, "Revoked"

    workspace = models.OneToOneField(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="runner_installation",
    )
    state = models.CharField(max_length=16, choices=State.choices, default=State.INACTIVE)
    consent_version = models.PositiveSmallIntegerField(default=0)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runner_installations_activated",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runner_installations_suspended",
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runner_installations_revoked",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_runner_installations"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["state", "updated_at"])]
        constraints = [
            models.CheckConstraint(
                check=(
                    ~models.Q(state=RunnerInstallationState.ACTIVE)
                    | (models.Q(consent_version__gte=1) & models.Q(activated_at__isnull=False))
                ),
                name="ext_runner_active_requires_consent",
            )
        ]


class RunnerAuditEvent(models.Model):
    """Append-only security audit event.

    Application-level mutation guards make accidental updates fail loudly. The
    service layer only writes allow-listed, non-secret metadata.
    """

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="runner_audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="runner_audit_events",
    )
    action = models.CharField(max_length=96)
    target_type = models.CharField(max_length=64)
    target_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableAuditEventQuerySet.as_manager()

    class Meta:
        db_table = "ext_runner_audit_events"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Runner audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Runner audit events are immutable.")
