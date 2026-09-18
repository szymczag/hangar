# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Turning a training already planned in the calendar into a Hangar Workshop.

The transitional problem this exists for: the next few months of training are
planned in the shared calendar, not in Hangar. The sweep makes Hangar *aware* of
them -- they block time and they count in the report -- but they are not work
items, so nothing can be attached to them. No checklist, no subtasks, no status,
no place for the client contact. That is the whole point of having them here.

Importing is deliberately a reviewed action rather than something the sweep does
on its own. A shared calendar carries plenty that is not a workshop, and undoing
a mistaken automatic import means deleting work items somebody may already have
written on.

Creating the Workshop links the invitation to the new session in the same
transaction. Without that the training would be counted twice the moment it
exists in both places: once as Hangar delivery, once as external training.
"""

import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from plane.db.models import Issue, IssueAssignee, ProjectMember, State
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.models import (
    GoogleTrainingEventLink,
    TrainingEventOccurrence,
    WorkshopSchedule,
    WorkshopSession,
)
from plane.ext.services.issue_types import ensure_project_workshop_type
from plane.utils.host import base_host

# Matching IssueCreateSerializer: below this a project member cannot hold work.
ASSIGNABLE_ROLE = 15


def occurrence_title(occurrence, *, zone="UTC"):
    """What the imported Workshop is called.

    The calendar title when there is one -- which is the reason titles are read
    at all, and why they are read only for events a rule already matched. When
    there is not, the rule's own label plus the date beats a row of work items
    all called the same thing.
    """
    if occurrence.encrypted_summary:
        title = decrypt_value(occurrence.encrypted_summary, occurrence.encryption_key_id).strip()
        if title:
            return title[:255]
    try:
        local = occurrence.starts_at.astimezone(ZoneInfo(zone))
    except (ValueError, ZoneInfoNotFoundError):
        local = occurrence.starts_at
    label = occurrence.rule_label or "Training"
    return f"{label} · {local:%Y-%m-%d}"[:255]


def pending_occurrences(workspace_id, *, start, end, trainer_ids=None):
    """Recognized trainings that are not yet a Workshop in Hangar.

    "Not yet" means no invitation link, not "no work item with a similar name":
    the link is the only statement anybody has made about these two things being
    the same training, and guessing from titles is how an import ends up
    attaching a session to the wrong workshop.
    """
    linked = GoogleTrainingEventLink.objects.filter(
        workspace_id=workspace_id,
        trainer_id=OuterRef("trainer_id"),
        event_key=OuterRef("event_key"),
    )
    queryset = (
        TrainingEventOccurrence.objects.filter(
            workspace_id=workspace_id,
            state=TrainingEventOccurrence.State.ACTIVE,
            starts_at__lt=end,
            ends_at__gt=start,
        )
        .annotate(is_linked=Exists(linked))
        .filter(is_linked=False)
        .select_related("trainer", "trainer_profile")
        .order_by("starts_at", "id")
    )
    if trainer_ids:
        queryset = queryset.filter(trainer_id__in=trainer_ids)
    return queryset


@transaction.atomic
def import_occurrence(occurrence, *, project, actor, request=None):
    """Create the Workshop this invitation describes, and link the two.

    Returns `(issue, reason)`. A reason means nothing was created: either the
    invitation is already linked, or the trainer cannot hold work in the chosen
    project, which is a decision for a person rather than something to paper
    over by assigning nobody.
    """
    already_linked = GoogleTrainingEventLink.objects.filter(
        workspace_id=occurrence.workspace_id,
        trainer_id=occurrence.trainer_id,
        event_key=occurrence.event_key,
    ).exists()
    if already_linked:
        return None, "already_imported"

    if not ProjectMember.objects.filter(
        project=project, member_id=occurrence.trainer_id, role__gte=ASSIGNABLE_ROLE, is_active=True
    ).exists():
        return None, "trainer_not_in_project"

    workshop_type = ensure_project_workshop_type(project)
    default_state = State.objects.filter(project=project, default=True).first()
    zone = occurrence.trainer_profile.timezone if occurrence.trainer_profile else "UTC"

    issue = Issue.objects.create(
        name=occurrence_title(occurrence, zone=zone),
        project=project,
        workspace_id=occurrence.workspace_id,
        state=default_state,
        type=workshop_type,
        start_date=occurrence.starts_at.date(),
        target_date=occurrence.ends_at.date(),
        created_by=actor,
        updated_by=actor,
    )
    IssueAssignee.objects.create(
        issue=issue,
        assignee_id=occurrence.trainer_id,
        project=project,
        workspace_id=occurrence.workspace_id,
        created_by=actor,
        updated_by=actor,
    )

    schedule = WorkshopSchedule.objects.create(
        issue=issue,
        starts_at=occurrence.starts_at,
        ends_at=occurrence.ends_at,
        created_by=actor,
        updated_by=actor,
    )
    session = WorkshopSession.objects.create(
        schedule=schedule,
        position=0,
        starts_at=occurrence.starts_at,
        ends_at=occurrence.ends_at,
        created_by=actor,
        updated_by=actor,
    )
    session.trainers.add(occurrence.trainer_id)

    # The link is what stops the same training being counted as Hangar delivery
    # and as external training at once, so it is created here rather than left
    # to the trainer to do by hand afterwards.
    GoogleTrainingEventLink.objects.create(
        workspace_id=occurrence.workspace_id,
        trainer_id=occurrence.trainer_id,
        event_key=occurrence.event_key,
        session=session,
        created_by=actor,
        updated_by=actor,
    )

    epoch = int(timezone.now().timestamp())
    origin = base_host(request=request, is_app=True) if request is not None else None
    issue_id = str(issue.id)
    project_id = str(project.id)
    payload = json.dumps({"name": issue.name}, cls=DjangoJSONEncoder)

    def announce():
        # Imported late so the module can be imported from a service:
        # plane.app.serializers imports plane.ext.services, and this task imports
        # the serializers back.
        from plane.bgtasks.issue_activities_task import issue_activity

        issue_activity.delay(
            type="issue.activity.created",
            requested_data=payload,
            current_instance=None,
            issue_id=issue_id,
            actor_id=str(actor.id),
            project_id=project_id,
            epoch=epoch,
            notification=True,
            origin=origin,
        )

    transaction.on_commit(announce)
    return issue, None


def import_occurrences(occurrences, *, project, actor, request=None):
    """Import several, reporting per row rather than failing the whole batch."""
    created, skipped = [], []
    for occurrence in occurrences:
        issue, reason = import_occurrence(occurrence, project=project, actor=actor, request=request)
        if issue is None:
            skipped.append({"occurrence_id": str(occurrence.id), "reason": reason})
        else:
            created.append({"occurrence_id": str(occurrence.id), "issue_id": str(issue.id), "name": issue.name})
    return {"created": created, "skipped": skipped}


def occurrence_payload(occurrence, *, with_title):
    return {
        "id": str(occurrence.id),
        "trainer_id": str(occurrence.trainer_id),
        "display_name": occurrence.trainer.display_name,
        "starts_at": occurrence.starts_at.isoformat(),
        "ends_at": occurrence.ends_at.isoformat(),
        "minutes": int((occurrence.ends_at - occurrence.starts_at).total_seconds() // 60),
        "status": occurrence.status,
        "rule_label": occurrence.rule_label,
        "title": occurrence_title(occurrence) if with_title else None,
    }


def parse_range(raw_from, raw_to):
    """Both bounds, timezone-aware, or an explanation of what is wrong."""
    start = _parse(raw_from)
    end = _parse(raw_to)
    if start is None or end is None or start >= end:
        return None, None, "from and to must be timezone-aware RFC3339 values."
    return start, end, None


def _parse(value):
    parsed = parse_datetime(value or "")
    if parsed is None or timezone.is_naive(parsed):
        return None
    return parsed
