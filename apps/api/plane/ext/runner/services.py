# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from plane.db.models import Workspace

from .constants import RUNNER_CONSENT_VERSION, RunnerAuditAction, RunnerInstallationState
from .models import RunnerAuditEvent, RunnerInstallation


class RunnerServiceError(Exception):
    code = "runner_error"


class RunnerDisabledError(RunnerServiceError):
    code = "runner_disabled"


class RunnerConsentError(RunnerServiceError):
    code = "runner_consent_required"


class RunnerTransitionError(RunnerServiceError):
    code = "invalid_runner_transition"


def runner_is_enabled() -> bool:
    """Runner remains unavailable unless an operator explicitly enables it."""

    return bool(getattr(settings, "RUNNER_ENABLED", False))


def require_runner_enabled() -> None:
    if not runner_is_enabled():
        raise RunnerDisabledError("Runner is not enabled on this instance.")


class RunnerInstallationService:
    @staticmethod
    def get(workspace: Workspace) -> RunnerInstallation | None:
        return RunnerInstallation.objects.filter(workspace=workspace).first()

    @staticmethod
    def _audit(
        *,
        installation: RunnerInstallation,
        actor,
        action: str,
        previous_state: str,
    ) -> None:
        RunnerAuditEvent.objects.create(
            workspace=installation.workspace,
            actor=actor,
            action=action,
            target_type="runner_installation",
            target_id=installation.id,
            metadata={
                "previous_state": previous_state,
                "state": installation.state,
                "consent_version": installation.consent_version,
            },
        )

    @classmethod
    @transaction.atomic
    def activate(
        cls,
        *,
        workspace: Workspace,
        actor,
        consent_version: int,
    ) -> tuple[RunnerInstallation, bool]:
        require_runner_enabled()
        if consent_version != RUNNER_CONSENT_VERSION:
            raise RunnerConsentError(f"Consent version {RUNNER_CONSENT_VERSION} must be accepted.")

        locked_workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
        installation = RunnerInstallation.objects.filter(workspace=locked_workspace).first()
        created = False
        if installation is None:
            created = True
            installation = RunnerInstallation(workspace=locked_workspace)
            installation.save(created_by_id=actor.id)

        if installation.state == RunnerInstallationState.REVOKED:
            raise RunnerTransitionError("A revoked Runner installation cannot be reactivated.")
        if installation.state == RunnerInstallationState.ACTIVE and installation.consent_version == consent_version:
            return installation, created

        previous_state = installation.state
        installation.state = RunnerInstallationState.ACTIVE
        installation.consent_version = consent_version
        installation.activated_by = actor
        installation.activated_at = timezone.now()
        installation.suspended_by = None
        installation.suspended_at = None
        installation.updated_by = actor
        installation.save(
            disable_auto_set_user=True,
            update_fields=[
                "state",
                "consent_version",
                "activated_by",
                "activated_at",
                "suspended_by",
                "suspended_at",
                "updated_by",
                "updated_at",
            ],
        )
        cls._audit(
            installation=installation,
            actor=actor,
            action=RunnerAuditAction.INSTALLATION_ACTIVATED,
            previous_state=previous_state,
        )
        return installation, created

    @classmethod
    @transaction.atomic
    def suspend(cls, *, workspace: Workspace, actor) -> tuple[RunnerInstallation, bool]:
        require_runner_enabled()
        Workspace.objects.select_for_update().get(pk=workspace.pk)
        installation = RunnerInstallation.objects.filter(workspace=workspace).first()
        if installation is None or installation.state == RunnerInstallationState.INACTIVE:
            raise RunnerTransitionError("Only an active Runner installation can be suspended.")
        if installation.state == RunnerInstallationState.REVOKED:
            raise RunnerTransitionError("A revoked Runner installation cannot be suspended.")
        if installation.state == RunnerInstallationState.SUSPENDED:
            return installation, False

        previous_state = installation.state
        installation.state = RunnerInstallationState.SUSPENDED
        installation.suspended_by = actor
        installation.suspended_at = timezone.now()
        installation.updated_by = actor
        installation.save(
            disable_auto_set_user=True,
            update_fields=[
                "state",
                "suspended_by",
                "suspended_at",
                "updated_by",
                "updated_at",
            ],
        )
        cls._audit(
            installation=installation,
            actor=actor,
            action=RunnerAuditAction.INSTALLATION_SUSPENDED,
            previous_state=previous_state,
        )
        return installation, True

    @classmethod
    @transaction.atomic
    def revoke(cls, *, workspace: Workspace, actor) -> tuple[RunnerInstallation, bool]:
        require_runner_enabled()
        Workspace.objects.select_for_update().get(pk=workspace.pk)
        installation = RunnerInstallation.objects.filter(workspace=workspace).first()
        if installation is None or installation.state == RunnerInstallationState.INACTIVE:
            raise RunnerTransitionError("An inactive Runner installation cannot be revoked.")
        if installation.state == RunnerInstallationState.REVOKED:
            return installation, False

        previous_state = installation.state
        installation.state = RunnerInstallationState.REVOKED
        installation.revoked_by = actor
        installation.revoked_at = timezone.now()
        installation.updated_by = actor
        installation.save(
            disable_auto_set_user=True,
            update_fields=[
                "state",
                "revoked_by",
                "revoked_at",
                "updated_by",
                "updated_at",
            ],
        )
        cls._audit(
            installation=installation,
            actor=actor,
            action=RunnerAuditAction.INSTALLATION_REVOKED,
            previous_state=previous_state,
        )
        return installation, True
