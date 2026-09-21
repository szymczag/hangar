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
from django.db import IntegrityError, transaction
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


class AlreadyImported(Exception):
    """Raised when a concurrent import won the race for the same training."""


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
            imported_issue__isnull=True,
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


def training_groups(occurrences):
    """Occurrences gathered into trainings, in the order they were given.

    An occurrence is one trainer's view of one training -- the record is unique
    per (workspace, trainer, event key) -- so a training delivered by two people
    arrives as two rows. The event key is derived from the event's own identity
    and not from who was invited, which makes it the same for everybody on the
    training, and that is what they are grouped by.

    Without this the listing showed a two-trainer training twice, and importing
    both rows created two Workshops for one training.
    """
    groups = {}
    for occurrence in occurrences:
        groups.setdefault(occurrence.event_key, []).append(occurrence)
    return list(groups.values())


@transaction.atomic
def import_training(event_key, *, workspace_id, project, actor, request=None):
    """Create the one Workshop a training describes, with every trainer on it.

    Returns `(issue, reason, skipped)`. With a reason, nothing was created: the
    training is already in Hangar, it no longer exists, or none of its trainers
    can hold work in the chosen project. `skipped` names the occurrences of
    trainers who could not be put on it -- the training is still created for
    the rest, and those rows stay in the listing, because that part of the
    training genuinely is not in Hangar yet.
    """
    # Every trainer's row, re-read under a lock. The listing filtered on these,
    # but a concurrent import of the same training, or a sweep retiring it in
    # between, must not be decided by what the client last saw.
    occurrences = list(
        TrainingEventOccurrence.objects.select_for_update()
        .select_related("trainer", "trainer_profile")
        .filter(workspace_id=workspace_id, event_key=event_key)
        .order_by("id")
    )
    if not occurrences:
        return None, "no_longer_active", []

    live = [row for row in occurrences if row.state == TrainingEventOccurrence.State.ACTIVE]
    if not live:
        # A cancelled or vanished invitation still sits in the table for its
        # retention period, so an id harvested from an earlier listing stays
        # usable unless the state is checked here rather than only in the query.
        return None, "no_longer_active", []

    pending = [row for row in live if row.imported_issue_id is None]
    linked = set(
        GoogleTrainingEventLink.objects.filter(
            workspace_id=workspace_id, event_key=event_key, trainer_id__in=[row.trainer_id for row in pending]
        ).values_list("trainer_id", flat=True)
    )
    pending = [row for row in pending if row.trainer_id not in linked]
    if not pending:
        return None, "already_imported", []

    members = set(
        ProjectMember.objects.filter(
            project=project,
            member_id__in=[row.trainer_id for row in pending],
            role__gte=ASSIGNABLE_ROLE,
            is_active=True,
        ).values_list("member_id", flat=True)
    )
    eligible = [row for row in pending if row.trainer_id in members]
    skipped = [row for row in pending if row.trainer_id not in members]
    if not eligible:
        return None, "trainer_not_in_project", []

    # Part of this training may already be a Workshop: an earlier import took the
    # trainers who could hold work in the project and left the rest listed. Those
    # join the Workshop that exists -- creating another would be the very
    # duplication this grouping exists to prevent, arriving by the back door.
    existing = next((row.imported_issue_id for row in live if row.imported_issue_id), None)
    if existing is not None:
        return _join_existing(
            existing, eligible, skipped, event_key=event_key, workspace_id=workspace_id, project=project, actor=actor
        )

    first = eligible[0]
    workshop_type = ensure_project_workshop_type(project)
    default_state = State.objects.filter(project=project, default=True).first()
    zone = first.trainer_profile.timezone if first.trainer_profile else "UTC"

    # Every row describes the same event, so they share a time and a title. The
    # first eligible one speaks for them all.
    issue = Issue.objects.create(
        name=occurrence_title(first, zone=zone),
        project=project,
        workspace_id=workspace_id,
        state=default_state,
        type=workshop_type,
        start_date=first.starts_at.date(),
        target_date=first.ends_at.date(),
        created_by=actor,
        updated_by=actor,
    )
    for row in eligible:
        IssueAssignee.objects.create(
            issue=issue,
            assignee_id=row.trainer_id,
            project=project,
            workspace_id=workspace_id,
            created_by=actor,
            updated_by=actor,
        )

    schedule = WorkshopSchedule.objects.create(
        issue=issue,
        starts_at=first.starts_at,
        ends_at=first.ends_at,
        created_by=actor,
        updated_by=actor,
    )
    # One session with every trainer on it -- not a session each. The training
    # is one event; splitting it would put the same afternoon in Hangar twice.
    session = WorkshopSession.objects.create(
        schedule=schedule,
        position=0,
        starts_at=first.starts_at,
        ends_at=first.ends_at,
        created_by=actor,
        updated_by=actor,
    )
    session.trainers.add(*[row.trainer_id for row in eligible])

    # One link per trainer, all to the same session. The link is what stops the
    # training being counted as Hangar delivery and as external training at
    # once, and it is keyed per trainer because each of them was invited
    # separately.
    try:
        for row in eligible:
            GoogleTrainingEventLink.objects.create(
                workspace_id=workspace_id,
                trainer_id=row.trainer_id,
                event_key=event_key,
                session=session,
                created_by=actor,
                updated_by=actor,
            )
    except IntegrityError:
        # Another import won the unique index between the check above and here.
        # That is the correct outcome, not a server error: the training already
        # exists in Hangar, and this transaction rolls back the duplicate.
        raise AlreadyImported from None

    TrainingEventOccurrence.objects.filter(pk__in=[row.pk for row in eligible]).update(
        imported_issue=issue, updated_at=timezone.now()
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
    return issue, None, skipped


def _join_existing(issue_id, eligible, skipped, *, event_key, workspace_id, project, actor):
    """Put the remaining trainers of a partly imported training on its Workshop."""
    link = (
        GoogleTrainingEventLink.objects.select_related("session")
        .filter(workspace_id=workspace_id, event_key=event_key)
        .first()
    )
    issue = Issue.objects.filter(pk=issue_id).first()
    if link is None or issue is None:
        # The Workshop or its session was removed since. Treat what is left as a
        # training nobody has imported rather than attaching it to nothing.
        return None, "no_longer_active", []
    if issue.project_id != project.id:
        # Joining a Workshop in a different project than the one chosen would
        # quietly move work somewhere the importer did not ask for.
        return None, "imported_elsewhere", []

    session = link.session
    session.trainers.add(*[row.trainer_id for row in eligible])
    present = set(issue.issue_assignee.values_list("assignee_id", flat=True))
    for row in eligible:
        if row.trainer_id not in present:
            IssueAssignee.objects.create(
                issue=issue,
                assignee_id=row.trainer_id,
                project=project,
                workspace_id=workspace_id,
                created_by=actor,
                updated_by=actor,
            )
    try:
        for row in eligible:
            GoogleTrainingEventLink.objects.create(
                workspace_id=workspace_id,
                trainer_id=row.trainer_id,
                event_key=event_key,
                session=session,
                created_by=actor,
                updated_by=actor,
            )
    except IntegrityError:
        raise AlreadyImported from None
    TrainingEventOccurrence.objects.filter(pk__in=[row.pk for row in eligible]).update(
        imported_issue=issue, updated_at=timezone.now()
    )
    return issue, None, skipped


def import_occurrences(occurrences, *, project, actor, request=None):
    """Import the trainings these rows belong to, reporting per training.

    Any row of a training imports the whole training: selecting one trainer's
    row of a two-trainer training means that training, and importing only that
    trainer's half would leave the other half to be imported later as a second
    Workshop -- the duplication this grouping exists to prevent.
    """
    created, skipped = [], []
    for group in training_groups(occurrences):
        head = group[0]
        try:
            issue, reason, left_out = import_training(
                head.event_key, workspace_id=head.workspace_id, project=project, actor=actor, request=request
            )
        except AlreadyImported:
            issue, reason, left_out = None, "already_imported", []
        if issue is None:
            skipped.extend({"occurrence_id": str(row.id), "reason": reason} for row in group)
            continue
        created.append(
            {
                "occurrence_id": str(head.id),
                "issue_id": str(issue.id),
                "name": issue.name,
                "trainer_ids": [str(value) for value in issue.issue_assignee.values_list("assignee_id", flat=True)],
            }
        )
        skipped.extend({"occurrence_id": str(row.id), "reason": "trainer_not_in_project"} for row in left_out)
    return {"created": created, "skipped": skipped}


def training_payload(group, *, with_title):
    """One listing row per training, naming everybody on it."""
    head = group[0]
    return {
        # Any occurrence id of the training imports all of it; the first is
        # offered so an older client that posts one id per row still works.
        "id": str(head.id),
        "occurrence_ids": [str(row.id) for row in group],
        "trainers": [
            {"trainer_id": str(row.trainer_id), "display_name": row.trainer.display_name, "status": row.status}
            for row in group
        ],
        # Kept for clients that render a single trainer per row.
        "trainer_id": str(head.trainer_id),
        "display_name": ", ".join(row.trainer.display_name for row in group),
        "starts_at": head.starts_at.isoformat(),
        "ends_at": head.ends_at.isoformat(),
        "minutes": int((head.ends_at - head.starts_at).total_seconds() // 60),
        # Confirmed only when everybody on it has accepted: one trainer who has
        # not answered is exactly what somebody importing needs to see.
        "status": "confirmed" if all(row.status == "confirmed" for row in group) else "pending",
        "rule_label": head.rule_label,
        "title": occurrence_title(head) if with_title else None,
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
