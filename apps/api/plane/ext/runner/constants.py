# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from enum import StrEnum

RUNNER_AUDIT_SCHEMA_VERSION = 1


class RunnerEffectiveState(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    CONSENT_REQUIRED = "consent_required"
