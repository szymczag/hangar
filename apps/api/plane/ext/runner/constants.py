# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from enum import StrEnum

from .consent import CURRENT_RUNNER_CONSENT


RUNNER_AUDIT_SCHEMA_VERSION = 1
RUNNER_CONSENT_VERSION = CURRENT_RUNNER_CONSENT.version


class RunnerEffectiveState(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    CONSENT_REQUIRED = "consent_required"
