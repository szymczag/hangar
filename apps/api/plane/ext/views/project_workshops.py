# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Whether a project holds training, decided by the project itself.

The Workshop type used to arrive in every project the moment anybody in the
workspace became a trainer. That put a training-specific type in the picker of
projects that have nothing to do with training, and made "which projects are the
training projects" a question nobody could answer from the data. A project now
opts in from its own settings, and only its administrators decide.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.db.models import Project
from plane.ext.models import CapacityAuditEvent
from plane.ext.services.issue_types import (
    WorkshopsInUse,
    disable_workshops,
    enable_workshops,
    workshop_count,
    workshops_enabled,
)
from plane.ext.views.capacity import _audit, _disabled
from plane.utils.permissions import ROLE, allow_permission


def _state(project):
    return {"enabled": workshops_enabled(project), "workshop_count": workshop_count(project)}


class ProjectWorkshopsEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request, slug, project_id):
        if response := _disabled():
            return response
        project = get_object_or_404(Project, workspace__slug=slug, pk=project_id)
        return Response(_state(project))

    @allow_permission([ROLE.ADMIN])
    @transaction.atomic
    def put(self, request, slug, project_id):
        if response := _disabled():
            return response
        enabled = request.data.get("enabled")
        if not isinstance(enabled, bool):
            return Response({"error": "enabled must be true or false."}, status=status.HTTP_400_BAD_REQUEST)
        project = get_object_or_404(Project.objects.select_for_update(), workspace__slug=slug, pk=project_id)

        if enabled:
            enable_workshops(project)
            action = CapacityAuditEvent.Action.WORKSHOPS_ENABLED
        else:
            try:
                disable_workshops(project)
            except WorkshopsInUse:
                count = workshop_count(project)
                return Response(
                    {
                        "error": (
                            f"This project still holds {count} Workshop{'s' if count != 1 else ''}. "
                            "Move them to another project or change their type before turning Workshops off."
                        ),
                        "code": "workshops_in_use",
                        "workshop_count": count,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            action = CapacityAuditEvent.Action.WORKSHOPS_DISABLED

        _audit(request, workspace_id=project.workspace_id, action=action, metadata={"project_id": str(project.id)})
        return Response(_state(project))
