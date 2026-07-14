# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.core.exceptions import ValidationError
from django.db import models


class ImmutableAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Runner audit events are immutable.")

    def delete(self):
        raise ValidationError("Runner audit events are immutable.")


class RunnerInstallationState(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REVOKED = "revoked", "Revoked"


class RunnerAuditAction(models.TextChoices):
    INSTALLATION_ACTIVATED = "runner.installation.activated", "Installation activated"
    INSTALLATION_REACTIVATED = "runner.installation.reactivated", "Installation reactivated"
    CONSENT_RENEWED = "runner.installation.consent_renewed", "Consent renewed"
    INSTALLATION_SUSPENDED = "runner.installation.suspended", "Installation suspended"
    INSTALLATION_REVOKED = "runner.installation.revoked", "Installation revoked"


class RunnerAuditTarget(models.TextChoices):
    INSTALLATION = "runner_installation", "Runner installation"


class RunnerInstallation(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    workspace = models.OneToOneField(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="runner_installation",
    )
    state = models.CharField(max_length=16, choices=RunnerInstallationState.choices)
    consent_version = models.PositiveSmallIntegerField()
    consent_document = models.CharField(max_length=128)
    consent_digest = models.CharField(max_length=64)
    activated_by = models.UUIDField()
    activated_at = models.DateTimeField()
    suspended_by = models.UUIDField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.UUIDField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_runner_installations"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["state", "updated_at"])]
        constraints = [
            models.CheckConstraint(
                check=models.Q(state__in=RunnerInstallationState.values),
                name="ext_runner_installation_valid_state",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(consent_version__gte=1) & ~models.Q(consent_document="") & ~models.Q(consent_digest="")
                ),
                name="ext_runner_installation_consent",
            ),
            models.CheckConstraint(
                check=models.Q(consent_digest__regex=r"^[0-9a-f]{64}$"),
                name="ext_runner_installation_consent_digest",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(state=RunnerInstallationState.ACTIVE, suspended_by__isnull=True, suspended_at__isnull=True)
                    | models.Q(
                        state=RunnerInstallationState.SUSPENDED,
                        suspended_by__isnull=False,
                        suspended_at__isnull=False,
                    )
                    | (
                        models.Q(state=RunnerInstallationState.REVOKED)
                        & (
                            models.Q(suspended_by__isnull=True, suspended_at__isnull=True)
                            | models.Q(suspended_by__isnull=False, suspended_at__isnull=False)
                        )
                    )
                ),
                name="ext_runner_installation_suspension",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(state=RunnerInstallationState.REVOKED, revoked_by__isnull=False, revoked_at__isnull=False)
                    | (
                        ~models.Q(state=RunnerInstallationState.REVOKED)
                        & models.Q(revoked_by__isnull=True, revoked_at__isnull=True)
                    )
                ),
                name="ext_runner_installation_revocation",
            ),
        ]


class RunnerAuditEvent(models.Model):
    """Append-only security audit event.

    Application-level mutation guards make accidental updates fail loudly. The
    service layer only writes allow-listed, non-secret metadata.
    """

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workspace_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField(db_index=True)
    action = models.CharField(max_length=96, choices=RunnerAuditAction.choices)
    target_type = models.CharField(max_length=64, choices=RunnerAuditTarget.choices)
    target_id = models.UUIDField()
    schema_version = models.PositiveSmallIntegerField(default=1)
    request_id = models.CharField(max_length=128)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableAuditEventQuerySet.as_manager()

    class Meta:
        db_table = "ext_runner_audit_events"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace_id", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(action__in=RunnerAuditAction.values),
                name="ext_runner_audit_valid_action",
            ),
            models.CheckConstraint(
                check=models.Q(target_type__in=RunnerAuditTarget.values),
                name="ext_runner_audit_valid_target",
            ),
            models.CheckConstraint(
                check=models.Q(schema_version__gte=1),
                name="ext_runner_audit_schema_version",
            ),
            models.CheckConstraint(
                check=models.Q(request_id__regex=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"),
                name="ext_runner_audit_request_id",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Runner audit events are immutable.")
        if not isinstance(self.metadata, dict):
            raise ValidationError("Runner audit metadata must be an object.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Runner audit events are immutable.")
