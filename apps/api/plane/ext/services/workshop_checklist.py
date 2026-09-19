# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Turning a checklist template into a Workshop's subtasks.

Subtasks are created one at a time through `Issue.objects.create()` rather than
`bulk_create`. That is deliberate: `Issue.save()` takes the project advisory
lock, allocates `sequence_id` and `sort_order`, derives `description_stripped`
and writes the `IssueSequence` row. `bulk_create` skips all of it, which is why
the bulk copy path (`plane.ext.services.work_item_copy`) has to reimplement the
whole ceremony by hand. A checklist is at most a few dozen rows, so paying for
one INSERT each buys correctness for free.
"""

import json
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, ProjectMember, State
from plane.ext.models import (
    TrainerProfile,
    WorkshopChecklistOrigin,
    WorkshopRoleMember,
    WorkshopSchedule,
)
from plane.ext.services.work_items import project_default_issue_type, validate_work_item_assignment
from plane.utils.host import base_host

# The role floor an assignee must clear, matching IssueCreateSerializer. A guest
# can be a member of the project without being assignable work.
ASSIGNABLE_ROLE = 15


def _workshop_timezone(issue):
    """The zone a workshop's dates are read in.

    A due date is a local calendar day, so "seven days before" has to be counted
    in the zone the people involved live in, not in UTC. The workshop's own
    trainers are the closest thing to that; their profile already resolves to
    the connected Google calendar's zone when there is one.
    """
    from plane.ext.capacity.timezones import trainer_timezone

    trainer = (
        TrainerProfile.objects.filter(
            workspace_id=issue.workspace_id,
            user_id__in=issue.issue_assignee.values_list("assignee_id", flat=True),
            status=TrainerProfile.Status.ACTIVE,
        )
        .select_related("user")
        .prefetch_related("calendar_selection__credential")
        .order_by("id")
        .first()
    )
    if trainer is None:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(trainer_timezone(trainer)[0])
    except (ValueError, ZoneInfoNotFoundError):
        return ZoneInfo("UTC")


def workshop_anchor(issue):
    """When the workshop actually happens, or `None` while it is unscheduled."""
    schedule = WorkshopSchedule.objects.filter(issue=issue).first()
    if schedule is None:
        return None
    first_session = schedule.sessions.order_by("position", "starts_at").first()
    return first_session.starts_at if first_session else schedule.starts_at


def target_date_for(anchor, offset_days, zone):
    """The local calendar day `offset_days` from the workshop."""
    if anchor is None:
        return None
    return (anchor.astimezone(zone) + timedelta(days=offset_days)).date()


def _assignee_ids(item, *, workshop_trainer_ids, role_members):
    if item.assignee_mode == item.AssigneeMode.FIXED:
        return [item.assignee_id] if item.assignee_id else []
    if item.assignee_mode == item.AssigneeMode.WORKSHOP_TRAINER:
        return list(workshop_trainer_ids)
    if item.assignee_mode == item.AssigneeMode.ROLE:
        # Everyone currently holding the role. A role nobody holds yet leaves the
        # subtask unassigned rather than failing: an empty rota is a staffing
        # question, not a reason to refuse the whole checklist.
        return list(role_members.get(item.role_id, ()))
    return []


def _role_members(items):
    """Current holders of every role the template names, in a single query."""
    role_ids = {item.role_id for item in items if item.role_id}
    if not role_ids:
        return {}
    members = {role_id: [] for role_id in role_ids}
    rows = (
        WorkshopRoleMember.objects.filter(role_id__in=role_ids, deleted_at__isnull=True)
        .order_by("id")
        .values_list("role_id", "member_id")
    )
    for role_id, member_id in rows:
        members[role_id].append(member_id)
    return members


def _assignable(project_id, candidate_ids):
    if not candidate_ids:
        return set()
    return set(
        ProjectMember.objects.filter(
            project_id=project_id,
            member_id__in=candidate_ids,
            role__gte=ASSIGNABLE_ROLE,
            is_active=True,
        ).values_list("member_id", flat=True)
    )


@transaction.atomic
def apply_checklist_template(*, template, issue, actor, request=None):
    """Create the template's subtasks under `issue`, skipping ones already there.

    Idempotent by subtask name. Applying a template twice must not double the
    checklist, and applying it again after the template grew should add only
    what is missing -- both are things a coordinator will do by accident and on
    purpose respectively.

    Returns the created issues and the assignees that were dropped because they
    cannot hold work in this project, so the caller can say so rather than
    silently losing an assignment.
    """
    items = list(template.items.select_related("assignee", "role").order_by("position", "id"))
    if not items:
        return {"created": [], "skipped_assignees": []}

    existing_names = set(
        Issue.objects.filter(parent_id=issue.id, deleted_at__isnull=True).values_list("name", flat=True)
    )
    workshop_trainer_ids = list(
        TrainerProfile.objects.filter(
            workspace_id=issue.workspace_id,
            user_id__in=issue.issue_assignee.values_list("assignee_id", flat=True),
            status=TrainerProfile.Status.ACTIVE,
        )
        .order_by("id")
        .values_list("user_id", flat=True)
    )

    role_members = _role_members(items)
    requested = set()
    for item in items:
        requested.update(_assignee_ids(item, workshop_trainer_ids=workshop_trainer_ids, role_members=role_members))
    allowed = _assignable(issue.project_id, requested)
    skipped_assignees = sorted(str(value) for value in requested - allowed)

    anchor = workshop_anchor(issue)
    zone = _workshop_timezone(issue)
    default_state = State.objects.filter(project_id=issue.project_id, default=True).first()
    default_type = project_default_issue_type(issue.project_id)
    # Validate once: every child shares the same project, parent and type, so a
    # per-child call would ask the same question a few dozen times.
    validate_work_item_assignment(
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        issue_type=default_type,
        parent=issue,
    )

    created = []
    for item in items:
        if item.title in existing_names:
            continue
        child = Issue.objects.create(
            name=item.title,
            description_html=item.description or "<p></p>",
            parent=issue,
            project_id=issue.project_id,
            workspace_id=issue.workspace_id,
            state=default_state,
            type=default_type,
            target_date=target_date_for(anchor, item.offset_days, zone),
            created_by=actor,
            updated_by=actor,
        )
        assignee_ids = [
            value
            for value in _assignee_ids(item, workshop_trainer_ids=workshop_trainer_ids, role_members=role_members)
            if value in allowed
        ]
        if assignee_ids:
            try:
                IssueAssignee.objects.bulk_create(
                    [
                        IssueAssignee(
                            issue=child,
                            assignee_id=assignee_id,
                            project_id=issue.project_id,
                            workspace_id=issue.workspace_id,
                            created_by=actor,
                            updated_by=actor,
                        )
                        for assignee_id in assignee_ids
                    ],
                    batch_size=10,
                )
            except IntegrityError:
                pass
        WorkshopChecklistOrigin.objects.create(
            issue=child,
            workspace_id=issue.workspace_id,
            item=item,
            offset_days=item.offset_days,
            created_by=actor,
            updated_by=actor,
        )
        existing_names.add(item.title)
        created.append(child)

    if created:
        # Imported here, not at module scope: `plane.app.serializers` imports
        # `plane.ext.services`, and this task imports `plane.app.serializers`
        # back. At module scope that closes a cycle and the whole app fails to
        # boot on a partially initialized serializers module.
        from plane.bgtasks.issue_activities_task import issue_activity

        epoch = int(timezone.now().timestamp())
        origin = base_host(request=request, is_app=True) if request is not None else None
        # A subtask that appears from nowhere is a small mystery in a work item's
        # history, so each one announces itself the way a hand-created one would.
        payloads = [
            {
                "issue_id": str(child.id),
                "requested_data": json.dumps({"name": child.name, "parent_id": str(issue.id)}, cls=DjangoJSONEncoder),
            }
            for child in created
        ]
        transaction.on_commit(
            lambda: [
                issue_activity.delay(
                    type="issue.activity.created",
                    requested_data=payload["requested_data"],
                    current_instance=None,
                    issue_id=payload["issue_id"],
                    actor_id=str(actor.id),
                    project_id=str(issue.project_id),
                    epoch=epoch,
                    notification=True,
                    origin=origin,
                )
                for payload in payloads
            ]
        )

    return {"created": created, "skipped_assignees": skipped_assignees}


def backfill_target_dates(issue):
    """Give the checklist its dates once the workshop has one.

    Subtasks created before the workshop was scheduled have no due date, because
    at that point there was nothing to count from. Scheduling is that moment, so
    it fills them in -- and only them: a date someone has since set by hand is
    their decision and is left alone.
    """
    anchor = workshop_anchor(issue)
    if anchor is None:
        return 0
    zone = _workshop_timezone(issue)
    origins = WorkshopChecklistOrigin.objects.filter(
        issue__parent_id=issue.id,
        issue__target_date__isnull=True,
        issue__deleted_at__isnull=True,
    ).select_related("issue")
    updated = []
    for origin in origins:
        origin.issue.target_date = target_date_for(anchor, origin.offset_days, zone)
        updated.append(origin.issue)
    if updated:
        Issue.objects.bulk_update(updated, ["target_date", "updated_at"])
    return len(updated)
