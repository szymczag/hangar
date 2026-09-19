# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.db.models import Workspace, ProjectMember
from plane.ext.models import (
    GoogleTrainingEventLink,
    GoogleTrainingRule,
    TrainerProfile,
    TrainingEventOccurrence,
    WorkshopSession,
)
from plane.ext.capacity.crypto import encrypt_value, decrypt_value
from plane.ext.capacity.training_events import training_events
from plane.ext.views.capacity import _disabled
from plane.utils.permissions import ROLE, allow_permission

logger = logging.getLogger(__name__)


class GoogleTrainingRulesEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug, rule_id=None):
        if rule_id is not None:
            return Response(status=405)
        if response := _disabled():
            return response
        rows = GoogleTrainingRule.objects.filter(workspace__slug=slug).order_by("label", "id")
        return Response(
            {
                "results": [
                    {
                        "id": str(row.id),
                        "label": row.label,
                        "calendar_id": decrypt_value(row.encrypted_calendar_id, row.encryption_key_id),
                        "organizer": decrypt_value(row.encrypted_organizer, row.encryption_key_id),
                    }
                    for row in rows
                ]
            }
        )

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    @transaction.atomic
    def post(self, request, slug, rule_id=None):
        if rule_id is not None:
            return Response(status=405)
        if response := _disabled():
            return response
        workspace = get_object_or_404(Workspace.objects.select_for_update(), slug=slug)
        label, calendar_id, organizer = (request.data.get(key) for key in ("label", "calendar_id", "organizer"))
        if not all(isinstance(value, str) and value.strip() for value in (label, calendar_id, organizer)):
            return Response({"error": "Label, calendar ID and organizer email are required."}, status=400)
        if len(label) > 100 or len(calendar_id) > 1024 or len(organizer) > 254:
            return Response({"error": "A rule value is too long."}, status=400)
        try:
            validate_email(organizer.strip())
        except ValidationError:
            return Response({"error": "Enter a valid organizer email."}, status=400)
        if GoogleTrainingRule.objects.filter(workspace=workspace).count() >= 10:
            return Response({"error": "Use at most ten training rules."}, status=400)
        encrypted_calendar, key_id = encrypt_value(calendar_id.strip())
        row = GoogleTrainingRule.objects.create(
            workspace=workspace,
            label=label.strip(),
            encrypted_calendar_id=encrypted_calendar,
            encrypted_organizer=encrypt_value(organizer.strip().casefold())[0],
            encryption_key_id=key_id,
        )
        return Response({"id": str(row.id)}, status=201)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    @transaction.atomic
    def delete(self, request, slug, rule_id=None):
        if rule_id is None:
            return Response(status=405)
        if response := _disabled():
            return response
        rule = get_object_or_404(GoogleTrainingRule, workspace__slug=slug, id=rule_id)
        # Retire this rule's occurrences before the rule goes.
        #
        # Deleting is soft, and the soft-delete cascade nulls SET_NULL relations
        # (`bgtasks/deletion_task.py`), so the occurrences would survive with no
        # rule at all. Both sweep paths that retire an occurrence -- cancellation
        # and the full rescan -- select on the rule, so nothing could ever reach
        # them again: they would keep counting in the report and keep being
        # offered for import, for a calendar Hangar no longer recognizes.
        #
        # Re-adding the rule re-adopts them, because the occurrence key does not
        # depend on the rule.
        retired = TrainingEventOccurrence.objects.filter(rule=rule, state=TrainingEventOccurrence.State.ACTIVE).update(
            state=TrainingEventOccurrence.State.DISAPPEARED, updated_at=timezone.now()
        )
        rule.delete()
        logger.info("Training rule removed", extra={"rule_id": str(rule_id), "retired_occurrences": retired})
        return Response(status=204)


class GoogleTrainingLinkEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug, event_key=None):
        if event_key is not None:
            return Response(status=405)
        if response := _disabled():
            return response
        try:
            session_id = UUID(str(request.data.get("session_id")))
        except (ValueError, TypeError):
            return Response({"error": "Select a valid Workshop session."}, status=400)
        session = get_object_or_404(
            WorkshopSession.objects.select_related("schedule"),
            id=session_id,
            schedule__workspace__slug=slug,
            trainers=request.user,
        )
        if not ProjectMember.objects.filter(
            project_id=session.schedule.project_id, member=request.user, is_active=True
        ).exists():
            return Response({"error": "Workshop project access is required."}, status=403)
        trainer = get_object_or_404(TrainerProfile, workspace__slug=slug, user=request.user)
        events, freshness = training_events(trainer, session.starts_at, session.ends_at, force=True)
        key = request.data.get("event_key")
        if freshness != "fresh" or not any(item["key"] == key for item in events):
            return Response({"error": "A fresh, overlapping invitation for this trainer is required."}, status=409)
        GoogleTrainingEventLink.objects.update_or_create(
            workspace_id=trainer.workspace_id, trainer=request.user, event_key=key, defaults={"session": session}
        )
        return Response({"linked": True})

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def delete(self, request, slug, event_key=None):
        if event_key is None:
            return Response(status=405)
        if response := _disabled():
            return response
        GoogleTrainingEventLink.objects.filter(workspace__slug=slug, trainer=request.user, event_key=event_key).delete()
        return Response(status=204)
