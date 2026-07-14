# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

RUNNER_CONSENT_VERSION = 1


class RunnerInstallationState:
    INACTIVE = "inactive"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class RunnerAuditAction:
    INSTALLATION_ACTIVATED = "runner.installation.activated"
    INSTALLATION_SUSPENDED = "runner.installation.suspended"
    INSTALLATION_REVOKED = "runner.installation.revoked"
