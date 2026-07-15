# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings


def todoist_imports_enabled() -> bool:
    """Return the process-level containment gate for Todoist imports."""

    return bool(getattr(settings, "TODOIST_IMPORTS_ENABLED", False))
