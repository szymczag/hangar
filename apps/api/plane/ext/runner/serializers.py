# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework import serializers

from .constants import RUNNER_CONSENT_VERSION, RunnerInstallationState
from .models import RunnerInstallation


class RunnerActivationSerializer(serializers.Serializer):
    consent_version = serializers.IntegerField(min_value=1)


class RunnerInstallationSerializer(serializers.ModelSerializer):
    required_consent_version = serializers.SerializerMethodField()

    class Meta:
        model = RunnerInstallation
        fields = [
            "id",
            "state",
            "consent_version",
            "required_consent_version",
            "activated_by",
            "activated_at",
            "suspended_by",
            "suspended_at",
            "revoked_by",
            "revoked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_required_consent_version(self, _instance) -> int:
        return RUNNER_CONSENT_VERSION


def inactive_installation_payload() -> dict:
    return {
        "id": None,
        "state": RunnerInstallationState.INACTIVE,
        "consent_version": 0,
        "required_consent_version": RUNNER_CONSENT_VERSION,
        "activated_by": None,
        "activated_at": None,
        "suspended_by": None,
        "suspended_at": None,
        "revoked_by": None,
        "revoked_at": None,
        "created_at": None,
        "updated_at": None,
    }
