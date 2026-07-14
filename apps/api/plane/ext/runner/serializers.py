# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from rest_framework import serializers

from .constants import RunnerEffectiveState
from .models import RunnerInstallation, RunnerInstallationState
from .services import (
    current_runner_consent,
    installation_effective_state,
    installation_has_current_consent,
    installation_is_effectively_active,
)


class RunnerActivationSerializer(serializers.Serializer):
    consent_version = serializers.IntegerField(min_value=1)
    consent_digest = serializers.RegexField(regex=r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RunnerInstallationSnapshot:
    id: UUID | None
    state: str
    lifecycle_state: str | None
    consent_version: int | None
    consent_document: str | None
    consent_digest: str | None
    required_consent_version: int
    required_consent_document: str
    required_consent_digest: str
    required_consent_text: str
    consent_required: bool
    is_effectively_active: bool
    activated_by: UUID | None
    activated_at: datetime | None
    suspended_by: UUID | None
    suspended_at: datetime | None
    revoked_by: UUID | None
    revoked_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class RunnerInstallationSerializer(serializers.Serializer):
    id = serializers.UUIDField(allow_null=True)
    state = serializers.ChoiceField(choices=[state.value for state in RunnerEffectiveState])
    lifecycle_state = serializers.ChoiceField(choices=RunnerInstallationState.values, allow_null=True)
    consent_version = serializers.IntegerField(allow_null=True)
    consent_document = serializers.CharField(allow_null=True)
    consent_digest = serializers.CharField(allow_null=True)
    required_consent_version = serializers.IntegerField()
    required_consent_document = serializers.CharField()
    required_consent_digest = serializers.CharField()
    required_consent_text = serializers.CharField()
    consent_required = serializers.BooleanField()
    is_effectively_active = serializers.BooleanField()
    activated_by = serializers.UUIDField(allow_null=True)
    activated_at = serializers.DateTimeField(allow_null=True)
    suspended_by = serializers.UUIDField(allow_null=True)
    suspended_at = serializers.DateTimeField(allow_null=True)
    revoked_by = serializers.UUIDField(allow_null=True)
    revoked_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    updated_at = serializers.DateTimeField(allow_null=True)


def installation_snapshot(installation: RunnerInstallation | None) -> RunnerInstallationSnapshot:
    consent = current_runner_consent()
    if installation is None:
        return RunnerInstallationSnapshot(
            id=None,
            state=RunnerEffectiveState.INACTIVE,
            lifecycle_state=None,
            consent_version=None,
            consent_document=None,
            consent_digest=None,
            required_consent_version=consent.version,
            required_consent_document=consent.document_id,
            required_consent_digest=consent.digest,
            required_consent_text=consent.text,
            consent_required=True,
            is_effectively_active=False,
            activated_by=None,
            activated_at=None,
            suspended_by=None,
            suspended_at=None,
            revoked_by=None,
            revoked_at=None,
            created_at=None,
            updated_at=None,
        )

    has_current_consent = installation_has_current_consent(installation)
    return RunnerInstallationSnapshot(
        id=installation.id,
        state=installation_effective_state(installation),
        lifecycle_state=installation.state,
        consent_version=installation.consent_version,
        consent_document=installation.consent_document,
        consent_digest=installation.consent_digest,
        required_consent_version=consent.version,
        required_consent_document=consent.document_id,
        required_consent_digest=consent.digest,
        required_consent_text=consent.text,
        consent_required=not has_current_consent,
        is_effectively_active=installation_is_effectively_active(installation),
        activated_by=installation.activated_by,
        activated_at=installation.activated_at,
        suspended_by=installation.suspended_by,
        suspended_at=installation.suspended_at,
        revoked_by=installation.revoked_by,
        revoked_at=installation.revoked_at,
        created_at=installation.created_at,
        updated_at=installation.updated_at,
    )
