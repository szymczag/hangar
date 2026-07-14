# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from plane.app.permissions import ROLE
from plane.db.models import User, Workspace, WorkspaceMember

from .consent import CURRENT_RUNNER_CONSENT, RunnerConsentContract
from .constants import RUNNER_AUDIT_SCHEMA_VERSION, RunnerEffectiveState
from .models import (
    RunnerAuditAction,
    RunnerAuditEvent,
    RunnerAuditTarget,
    RunnerInstallation,
    RunnerInstallationState,
)


class RunnerServiceError(Exception):
    code = "runner_error"


class RunnerDisabledError(RunnerServiceError):
    code = "runner_disabled"


class RunnerPermissionError(RunnerServiceError):
    code = "runner_admin_required"


class RunnerConsentError(RunnerServiceError):
    code = "runner_consent_required"


class RunnerTransitionError(RunnerServiceError):
    code = "invalid_runner_transition"


@dataclass(frozen=True, slots=True)
class RunnerTransitionResult:
    installation: RunnerInstallation
    created: bool
    changed: bool


def current_runner_consent() -> RunnerConsentContract:
    return CURRENT_RUNNER_CONSENT


def runner_is_enabled() -> bool:
    """Return the process-level outer gate.

    This environment setting is deliberately not described as an immediate
    runtime kill switch; workers and dispatchers will require a durable gate.
    """

    return bool(getattr(settings, "RUNNER_ENABLED", False))


def require_runner_enabled() -> None:
    if not runner_is_enabled():
        raise RunnerDisabledError("Runner is not enabled on this instance.")


def installation_has_current_consent(installation: RunnerInstallation) -> bool:
    consent = current_runner_consent()
    return (
        installation.consent_version == consent.version
        and installation.consent_document == consent.document_id
        and installation.consent_digest == consent.digest
    )


def installation_is_effectively_active(installation: RunnerInstallation | None) -> bool:
    return bool(
        runner_is_enabled()
        and installation is not None
        and installation.state == RunnerInstallationState.ACTIVE
        and installation_has_current_consent(installation)
    )


def installation_effective_state(installation: RunnerInstallation | None) -> str:
    if installation is None:
        return RunnerEffectiveState.INACTIVE
    if installation.state == RunnerInstallationState.ACTIVE and not installation_has_current_consent(installation):
        return RunnerEffectiveState.CONSENT_REQUIRED
    return installation.state


class RunnerInstallationService:
    @staticmethod
    def _require_admin(*, workspace_id, actor: User, lock: bool = False) -> None:
        if actor is None or not actor.is_authenticated:
            raise RunnerPermissionError("An active workspace Admin is required.")

        memberships = WorkspaceMember.objects.filter(
            workspace_id=workspace_id,
            member_id=actor.id,
            role=ROLE.ADMIN.value,
            is_active=True,
        )
        if lock:
            memberships = memberships.select_for_update()
        if not memberships.exists():
            raise RunnerPermissionError("An active workspace Admin is required.")

    @classmethod
    def authorize_admin(cls, *, workspace: Workspace, actor: User) -> None:
        require_runner_enabled()
        cls._require_admin(workspace_id=workspace.id, actor=actor)

    @classmethod
    def get_for_admin(cls, *, workspace: Workspace, actor: User) -> RunnerInstallation | None:
        cls.authorize_admin(workspace=workspace, actor=actor)
        return RunnerInstallation.objects.filter(workspace=workspace).first()

    @staticmethod
    def require_effectively_active(*, workspace: Workspace) -> RunnerInstallation:
        require_runner_enabled()
        installation = RunnerInstallation.objects.filter(workspace=workspace).first()
        if not installation_is_effectively_active(installation):
            raise RunnerTransitionError("Runner is not active with the current consent contract.")
        return installation

    @staticmethod
    def _audit(
        *,
        installation: RunnerInstallation,
        actor: User,
        action: RunnerAuditAction,
        previous_state: str,
    ) -> None:
        consent = current_runner_consent()
        metadata = {
            "previous_state": previous_state,
            "state": installation.state,
            "consent_version": installation.consent_version,
            "consent_document": installation.consent_document,
            "consent_digest": installation.consent_digest,
            "required_consent_version": consent.version,
        }
        RunnerAuditEvent.objects.create(
            workspace_id=installation.workspace_id,
            actor_id=actor.id,
            action=action,
            target_type=RunnerAuditTarget.INSTALLATION,
            target_id=installation.id,
            schema_version=RUNNER_AUDIT_SCHEMA_VERSION,
            metadata=metadata,
        )

    @classmethod
    @transaction.atomic
    def activate(
        cls,
        *,
        workspace: Workspace,
        actor: User,
        consent_version: int,
        consent_digest: str,
    ) -> RunnerTransitionResult:
        require_runner_enabled()
        consent = current_runner_consent()
        if consent_version != consent.version or consent_digest != consent.digest:
            raise RunnerConsentError(
                f"Consent version {consent.version} with digest {consent.digest} must be accepted."
            )

        locked_workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
        cls._require_admin(workspace_id=locked_workspace.id, actor=actor, lock=True)
        installation = RunnerInstallation.objects.filter(workspace=locked_workspace).first()
        now = timezone.now()

        if installation is None:
            installation = RunnerInstallation.objects.create(
                workspace=locked_workspace,
                state=RunnerInstallationState.ACTIVE,
                consent_version=consent.version,
                consent_document=consent.document_id,
                consent_digest=consent.digest,
                activated_by=actor.id,
                activated_at=now,
            )
            cls._audit(
                installation=installation,
                actor=actor,
                action=RunnerAuditAction.INSTALLATION_ACTIVATED,
                previous_state=RunnerEffectiveState.INACTIVE,
            )
            return RunnerTransitionResult(installation=installation, created=True, changed=True)

        if installation.state == RunnerInstallationState.REVOKED:
            raise RunnerTransitionError("A revoked Runner installation cannot be reactivated.")
        if installation.state == RunnerInstallationState.ACTIVE and installation_has_current_consent(installation):
            return RunnerTransitionResult(installation=installation, created=False, changed=False)

        previous_state = installation_effective_state(installation)
        action = (
            RunnerAuditAction.CONSENT_RENEWED
            if installation.state == RunnerInstallationState.ACTIVE
            else RunnerAuditAction.INSTALLATION_REACTIVATED
        )
        installation.state = RunnerInstallationState.ACTIVE
        installation.consent_version = consent.version
        installation.consent_document = consent.document_id
        installation.consent_digest = consent.digest
        installation.activated_by = actor.id
        installation.activated_at = now
        installation.suspended_by = None
        installation.suspended_at = None
        installation.save(
            update_fields=[
                "state",
                "consent_version",
                "consent_document",
                "consent_digest",
                "activated_by",
                "activated_at",
                "suspended_by",
                "suspended_at",
                "updated_at",
            ]
        )
        cls._audit(
            installation=installation,
            actor=actor,
            action=action,
            previous_state=previous_state,
        )
        return RunnerTransitionResult(installation=installation, created=False, changed=True)

    @classmethod
    @transaction.atomic
    def suspend(cls, *, workspace: Workspace, actor: User) -> RunnerTransitionResult:
        require_runner_enabled()
        locked_workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
        cls._require_admin(workspace_id=locked_workspace.id, actor=actor, lock=True)
        installation = RunnerInstallation.objects.filter(workspace=locked_workspace).first()
        if installation is None:
            raise RunnerTransitionError("Runner has not been activated.")
        if installation.state == RunnerInstallationState.REVOKED:
            raise RunnerTransitionError("A revoked Runner installation cannot be suspended.")
        if installation.state == RunnerInstallationState.SUSPENDED:
            return RunnerTransitionResult(installation=installation, created=False, changed=False)

        previous_state = installation_effective_state(installation)
        installation.state = RunnerInstallationState.SUSPENDED
        installation.suspended_by = actor.id
        installation.suspended_at = timezone.now()
        installation.save(
            update_fields=[
                "state",
                "suspended_by",
                "suspended_at",
                "updated_at",
            ]
        )
        cls._audit(
            installation=installation,
            actor=actor,
            action=RunnerAuditAction.INSTALLATION_SUSPENDED,
            previous_state=previous_state,
        )
        return RunnerTransitionResult(installation=installation, created=False, changed=True)

    @classmethod
    @transaction.atomic
    def revoke(cls, *, workspace: Workspace, actor: User) -> RunnerTransitionResult:
        require_runner_enabled()
        locked_workspace = Workspace.objects.select_for_update().get(pk=workspace.pk)
        cls._require_admin(workspace_id=locked_workspace.id, actor=actor, lock=True)
        installation = RunnerInstallation.objects.filter(workspace=locked_workspace).first()
        if installation is None:
            raise RunnerTransitionError("Runner has not been activated.")
        if installation.state == RunnerInstallationState.REVOKED:
            return RunnerTransitionResult(installation=installation, created=False, changed=False)

        previous_state = installation_effective_state(installation)
        installation.state = RunnerInstallationState.REVOKED
        installation.revoked_by = actor.id
        installation.revoked_at = timezone.now()
        installation.save(
            update_fields=[
                "state",
                "revoked_by",
                "revoked_at",
                "updated_at",
            ]
        )
        cls._audit(
            installation=installation,
            actor=actor,
            action=RunnerAuditAction.INSTALLATION_REVOKED,
            previous_state=previous_state,
        )
        return RunnerTransitionResult(installation=installation, created=False, changed=True)
