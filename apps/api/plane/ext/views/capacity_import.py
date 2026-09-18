# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.db.models import Project, ProjectMember, Workspace
from plane.ext.models import TrainingEventOccurrence
from plane.ext.services.training_import import (
    import_occurrences,
    occurrence_payload,
    parse_range,
    pending_occurrences,
)
from plane.ext.views.capacity import _disabled
from plane.utils.permissions import ROLE, allow_permission

# The same ceiling the report uses. A range nobody sweeps is a range with
# nothing in it, so a wider one only invites confusion.
MAX_RANGE = timedelta(days=400)
MAX_IMPORT_BATCH = 100


class TrainingImportEndpoint(BaseAPIView):
    """Trainings that exist in the calendar but not yet as work items.

    The transitional surface: while the next months of training live in the
    shared calendar, this is how they become Workshops that can carry a
    checklist, a status and a client contact.

    Administrator-only, like the training rules it depends on -- and because the
    listing carries calendar titles, which the rest of the product deliberately
    does not expose.
    """

    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        start, end, error = parse_range(request.GET.get("from"), request.GET.get("to"))
        if error:
            return Response({"error": error}, status=400)
        if end - start > MAX_RANGE:
            return Response({"error": "Range may not exceed 400 days."}, status=400)

        trainer_ids = [value for value in request.GET.get("trainer_ids", "").split(",") if value]
        try:
            trainer_ids = [str(UUID(value)) for value in trainer_ids]
        except ValueError:
            return Response({"error": "trainer_ids must be UUIDs."}, status=400)

        workspace = get_object_or_404(Workspace, slug=slug)
        occurrences = pending_occurrences(workspace.id, start=start, end=end, trainer_ids=trainer_ids)
        return Response(
            {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "results": [occurrence_payload(row, with_title=True) for row in occurrences[:500]],
            }
        )

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        if response := _disabled():
            return response
        try:
            project_id = UUID(str(request.data.get("project_id")))
        except (TypeError, ValueError):
            return Response({"error": "Choose a project for the imported workshops."}, status=400)
        project = get_object_or_404(Project, workspace__slug=slug, pk=project_id)
        # Workspace administration does not imply a seat in the project, and a
        # work item has to be created by somebody who belongs there.
        if not ProjectMember.objects.filter(project=project, member=request.user, is_active=True).exists():
            return Response({"error": "Join the project before importing into it."}, status=403)

        raw_ids = request.data.get("occurrence_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return Response({"error": "Select at least one training to import."}, status=400)
        if len(raw_ids) > MAX_IMPORT_BATCH:
            return Response({"error": f"Import at most {MAX_IMPORT_BATCH} trainings at a time."}, status=400)
        try:
            occurrence_ids = [UUID(str(value)) for value in raw_ids]
        except (TypeError, ValueError):
            return Response({"error": "occurrence_ids must be UUIDs."}, status=400)

        occurrences = list(
            TrainingEventOccurrence.objects.filter(
                workspace=project.workspace, id__in=occurrence_ids
            ).select_related("trainer", "trainer_profile")
        )
        if len(occurrences) != len(set(occurrence_ids)):
            return Response({"error": "Some selected trainings no longer exist."}, status=404)

        result = import_occurrences(occurrences, project=project, actor=request.user, request=request)
        return Response(result, status=201)
