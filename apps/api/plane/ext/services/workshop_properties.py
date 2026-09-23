# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The people a workshop is sold, run and delivered by.

A workshop has three roles that the product itself has to be able to find:
whoever sold it, whoever runs it as a project, and whoever delivers it. They are
ordinary member properties of the Workshop type, so a coordinator edits them in
the work item like any other field and can rename or reorder them -- but each
carries a `system_key`, so renaming a column does not hide the trainers from the
planner, the checklists or the calendar import.

Delivery is tied to the trainers, which is why the trainer property is the one
with consequences: sessions default their trainers from it, the checklist's
"workshop trainer" mode reads it, and everyone named in it becomes an assignee of
the work item. That last part is what keeps the rest of the subsystem working
unchanged -- the ledger, the planner and the schedule editor all ask the work
item's assignees who is busy, and they keep getting the same answer as before.
"""

from django.db import transaction

from plane.db.models import IssueAssignee, IssueType, ProjectMember
from plane.ext.models import IssueProperty, IssuePropertyValue, PropertyTypeChoices, TrainerProfile

# Matching IssueCreateSerializer: below this a project member cannot hold work.
ASSIGNABLE_ROLE = 15

# Display names are what a coordinator sees and may rename; the system key is
# what the code looks for. Sort order leaves room above for anything a workspace
# adds of its own.
SYSTEM_PROPERTIES = (
    {
        "system_key": IssueProperty.SystemKey.SALES,
        "display_name": "Sales",
        "description": "Who sold this training.",
        "is_multi": False,
        "sort_order": 1000,
    },
    {
        "system_key": IssueProperty.SystemKey.PROJECT_MANAGER,
        "display_name": "PM",
        "description": "Who runs this training as a project.",
        "is_multi": False,
        "sort_order": 2000,
    },
    {
        "system_key": IssueProperty.SystemKey.TRAINER,
        "display_name": "Trainers",
        "description": "Who delivers this training. Sessions start from this list.",
        "is_multi": True,
        "sort_order": 3000,
    },
)


@transaction.atomic
def ensure_workshop_properties(workshop_type):
    """Provision the three role properties on the Workshop type.

    Repairs as well as provisions, like the system types themselves: the
    property type and multiplicity are what the code depends on, so they are
    restored, while the display name, description and order stay the
    coordinator's to change.
    """
    provisioned = {}
    for spec in SYSTEM_PROPERTIES:
        prop = IssueProperty.objects.filter(
            issue_type=workshop_type, system_key=spec["system_key"], deleted_at__isnull=True
        ).first()
        if prop is None:
            prop = IssueProperty.objects.create(
                workspace_id=workshop_type.workspace_id,
                issue_type=workshop_type,
                system_key=spec["system_key"],
                display_name=_free_display_name(workshop_type, spec["display_name"]),
                description=spec["description"],
                property_type=PropertyTypeChoices.MEMBER,
                is_multi=spec["is_multi"],
                sort_order=spec["sort_order"],
            )
        else:
            IssueProperty.objects.filter(pk=prop.pk).update(
                property_type=PropertyTypeChoices.MEMBER, is_multi=spec["is_multi"], is_active=True
            )
            prop.refresh_from_db()
        provisioned[spec["system_key"]] = prop
    return provisioned


def _free_display_name(workshop_type, preferred):
    """A name nobody has taken, because the unique name per type is a constraint.

    A workspace that already added its own "Trainers" column to Workshops keeps
    it; the system property arrives beside it under a name that is free, and the
    coordinator can rename either afterwards.
    """
    taken = set(
        IssueProperty.objects.filter(issue_type=workshop_type, deleted_at__isnull=True).values_list(
            "display_name", flat=True
        )
    )
    if preferred not in taken:
        return preferred
    for suffix in range(2, 100):
        candidate = f"{preferred} ({suffix})"
        if candidate not in taken:
            return candidate
    return preferred[:240] + str(workshop_type.pk)[:12]


def workshop_property(issue_type, system_key):
    if not issue_type or issue_type.system_key != IssueType.SystemKey.WORKSHOP:
        return None
    return IssueProperty.objects.filter(issue_type=issue_type, system_key=system_key, deleted_at__isnull=True).first()


def workshop_trainer_ids(issue):
    """Who this workshop's trainer property names, in the order it names them.

    Empty for a workshop whose property has never been filled in -- every
    workshop that existed before the property did. Callers fall back to the
    assignees there, which is what the property will hold once anybody edits it.
    """
    prop = workshop_property(issue.type, IssueProperty.SystemKey.TRAINER)
    if prop is None:
        return []
    return list(
        IssuePropertyValue.objects.filter(issue=issue, property=prop, value_member__isnull=False)
        .order_by("created_at", "id")
        .values_list("value_member_id", flat=True)
    )


def delivering_trainer_ids(issue):
    """The trainers of a workshop: its property if filled in, else its assignees."""
    return workshop_trainer_ids(issue) or list(issue.issue_assignee.values_list("assignee_id", flat=True))


@transaction.atomic
def set_workshop_trainers(issue, user_ids, *, actor=None):
    """Name these people in the trainer property, replacing whoever it named.

    Used by the calendar import, where the invitation already says who delivers
    the training: leaving the coordinator to retype it is how the property ends
    up disagreeing with the sessions.
    """
    prop = workshop_property(issue.type, IssueProperty.SystemKey.TRAINER)
    if prop is None:
        return []
    ordered = list(dict.fromkeys(user_ids))
    IssuePropertyValue.objects.filter(issue=issue, property=prop).delete()
    IssuePropertyValue.objects.bulk_create(
        IssuePropertyValue(
            issue=issue,
            property=prop,
            project_id=issue.project_id,
            workspace_id=issue.workspace_id,
            value_member_id=user_id,
            created_by=actor,
            updated_by=actor,
        )
        for user_id in ordered
    )
    return ordered


@transaction.atomic
def sync_trainer_assignees(issue, *, actor=None):
    """Make everybody the trainer property names an assignee of the workshop.

    The rest of the subsystem asks the work item's assignees who is delivering
    it -- the ledger, the planner, the schedule editor. Rather than teach each of
    them about a new field, naming somebody as a trainer assigns them, which is
    also what a coordinator expects to see in the work item afterwards.

    People are never unassigned here: an assignee who is dropped from the
    property may still hold subtasks, and quietly removing them is a decision for
    a person. Whoever cannot hold work in this project is reported back rather
    than assigned.
    """
    if not issue.type_id or issue.type.system_key != IssueType.SystemKey.WORKSHOP:
        return {"assigned": [], "skipped": []}

    named = workshop_trainer_ids(issue)
    if not named:
        return {"assigned": [], "skipped": []}

    already = set(issue.issue_assignee.values_list("assignee_id", flat=True))
    wanted = [user_id for user_id in named if user_id not in already]
    if not wanted:
        return {"assigned": [], "skipped": []}

    assignable = set(
        ProjectMember.objects.filter(
            project_id=issue.project_id, member_id__in=wanted, role__gte=ASSIGNABLE_ROLE, is_active=True
        ).values_list("member_id", flat=True)
    )
    IssueAssignee.objects.bulk_create(
        [
            IssueAssignee(
                issue=issue,
                assignee_id=user_id,
                project_id=issue.project_id,
                workspace_id=issue.workspace_id,
                created_by=actor,
                updated_by=actor,
            )
            for user_id in wanted
            if user_id in assignable
        ],
        ignore_conflicts=True,
    )
    return {
        "assigned": [str(user_id) for user_id in wanted if user_id in assignable],
        "skipped": [str(user_id) for user_id in wanted if user_id not in assignable],
    }


def active_trainer_ids(workspace_id, user_ids):
    """Which of these people are active trainers in this workspace."""
    return set(
        TrainerProfile.objects.filter(
            workspace_id=workspace_id, user_id__in=list(user_ids), status=TrainerProfile.Status.ACTIVE
        ).values_list("user_id", flat=True)
    )
