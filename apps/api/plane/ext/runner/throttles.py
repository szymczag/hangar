# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.throttling import SimpleRateThrottle


class RunnerUserThrottle(SimpleRateThrottle):
    """Bound aggregate Runner traffic even when callers rotate workspace slugs."""

    def get_cache_key(self, request, _view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class RunnerWorkspaceThrottle(SimpleRateThrottle):
    """Rate-limit a user and workspace pair without trusting client IP headers."""

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None

        workspace_slug = view.kwargs.get("slug", "unknown")
        ident = f"{request.user.pk}:{workspace_slug}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class RunnerReadThrottle(RunnerWorkspaceThrottle):
    scope = "runner_read"


class RunnerMutationThrottle(RunnerWorkspaceThrottle):
    scope = "runner_mutation"


class RunnerUserReadThrottle(RunnerUserThrottle):
    scope = "runner_user_read"


class RunnerUserMutationThrottle(RunnerUserThrottle):
    scope = "runner_user_mutation"
