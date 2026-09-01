# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.apps import AppConfig


class ExtConfig(AppConfig):
    name = "plane.ext"
    verbose_name = "Hangar Extensions"

    def ready(self):
        # Registers the receiver that seeds a new member's home page from the
        # workspace defaults, which is what lets upstream's lazy seed stay
        # untouched (see plane/ext/signals/workspace_defaults.py).
        from plane.ext import signals  # noqa: F401
