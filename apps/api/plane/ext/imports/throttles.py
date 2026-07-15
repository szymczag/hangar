# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import math

from django.conf import settings
from django.core.cache import caches
from django_redis import get_redis_connection
from rest_framework.exceptions import APIException
from rest_framework.throttling import SimpleRateThrottle

from plane.db.models import Workspace


logger = logging.getLogger(__name__)


class TodoistThrottleUnavailable(APIException):
    status_code = 503
    default_detail = "Todoist import admission is temporarily unavailable."
    default_code = "todoist_import_throttle_unavailable"


class AtomicTodoistImportThrottle(SimpleRateThrottle):
    """Use one Redis operation to admit requests across API processes."""

    _INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
local ttl = redis.call('PTTL', KEYS[1])
if count == 1 or ttl < 0 then
    redis.call('PEXPIRE', KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""

    def allow_request(self, request, view):
        if not settings.TODOIST_IMPORTS_ENABLED or self.rate is None:
            return True

        cache_key = self.get_cache_key(request, view)
        if cache_key is None:
            return True

        redis_key = caches["default"].make_key(cache_key)
        window_milliseconds = max(1, math.ceil(self.duration * 1000))
        try:
            result = get_redis_connection("default").eval(
                self._INCREMENT_SCRIPT,
                1,
                redis_key,
                window_milliseconds,
            )
            count, ttl_milliseconds = int(result[0]), int(result[1])
        except Exception as error:
            logger.warning(
                "Todoist import throttle dependency unavailable",
                extra={"scope": self.scope, "error_type": type(error).__name__},
            )
            raise TodoistThrottleUnavailable from None

        self._wait_seconds = max(0, ttl_milliseconds) / 1000
        return count <= self.num_requests

    def wait(self):
        return self._wait_seconds


class TodoistImportUserThrottle(AtomicTodoistImportThrottle):
    """Bound authenticated-user traffic independently of workspace slugs."""

    def get_cache_key(self, request, _view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class TodoistImportWorkspaceThrottle(AtomicTodoistImportThrottle):
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
