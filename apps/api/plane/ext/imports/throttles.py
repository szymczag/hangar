# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from rest_framework.throttling import SimpleRateThrottle

from plane.db.models import Workspace


class TodoistImportUserThrottle(SimpleRateThrottle):
    """Bound authenticated-user traffic independently of workspace slugs."""

    def get_cache_key(self, request, _view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class TodoistImportWorkspaceThrottle(SimpleRateThrottle):
    """Bound aggregate workspace traffic using a server-resolved workspace ID."""

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        workspace_id = Workspace.objects.filter(slug=view.kwargs.get("slug")).values_list("id", flat=True).first()
        if workspace_id is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": workspace_id}


class TodoistPreviewUserThrottle(TodoistImportUserThrottle):
    scope = "todoist_preview_user"


class TodoistPreviewWorkspaceThrottle(TodoistImportWorkspaceThrottle):
    scope = "todoist_preview_workspace"


class TodoistExecuteUserThrottle(TodoistImportUserThrottle):
    scope = "todoist_execute_user"


class TodoistExecuteWorkspaceThrottle(TodoistImportWorkspaceThrottle):
    scope = "todoist_execute_workspace"
