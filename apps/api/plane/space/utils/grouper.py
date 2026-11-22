# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db.models import Q, UUIDField, Value, F, Case, When, JSONField, CharField
from django.db.models.functions import Cast, Coalesce, JSONObject, Concat
from django.db.models import QuerySet

from typing import List, Optional, Dict, Any, Union

# Module imports
from plane.db.models import (
    Cycle,
    Issue,
    Label,
    Module,
    Project,
    State,
)


def issue_queryset_grouper(
    queryset: QuerySet[Issue], group_by: Optional[str], sub_group_by: Optional[str]
) -> QuerySet[Issue]:
    # Fork (see FORK.md, S30): a published board's work items carry no
    # assignees, so there is no assignee annotation or grouping here.
    FIELD_MAPPER = {
        "label_ids": "labels__id",
        "module_ids": "issue_module__module_id",
    }

    GROUP_FILTER_MAPPER = {
        "labels__id": Q(label_issue__deleted_at__isnull=True),
        "issue_module__module_id": Q(issue_module__deleted_at__isnull=True),
    }

    for group_key in [group_by, sub_group_by]:
        if group_key in GROUP_FILTER_MAPPER:
            queryset = queryset.filter(GROUP_FILTER_MAPPER[group_key])

    annotations_map = {
        "label_ids": (
            "labels__id",
            ~Q(labels__id__isnull=True) & Q(label_issue__deleted_at__isnull=True),
        ),
        "module_ids": (
            "issue_module__module_id",
            ~Q(issue_module__module_id__isnull=True),
        ),
    }
    default_annotations = {
        key: Coalesce(
            ArrayAgg(field, order_by=field, distinct=True, filter=condition),
            Value([], output_field=ArrayField(UUIDField())),
        )
        for key, (field, condition) in annotations_map.items()
        if FIELD_MAPPER.get(key) != group_by or FIELD_MAPPER.get(key) != sub_group_by
    }

    return queryset.annotate(**default_annotations)


def issue_on_results(
    issues: QuerySet[Issue], group_by: Optional[str], sub_group_by: Optional[str]
) -> List[Dict[str, Any]]:
    # Fork (see FORK.md, S30): no assignee_ids and no created_by -- a published
    # board does not say who a work item is assigned to or who opened it.
    FIELD_MAPPER = {
        "labels__id": "label_ids",
        "issue_module__module_id": "module_ids",
    }

    original_list = ["label_ids", "module_ids"]

    required_fields = [
        "id",
        "name",
        "state_id",
        "sort_order",
        "estimate_point",
        "priority",
        "start_date",
        "target_date",
        "sequence_id",
        "project_id",
        "parent_id",
        "cycle_id",
        "state__group",
    ]

    if group_by in FIELD_MAPPER:
        original_list.remove(FIELD_MAPPER[group_by])
        original_list.append(group_by)

    if sub_group_by in FIELD_MAPPER:
        original_list.remove(FIELD_MAPPER[sub_group_by])
        original_list.append(sub_group_by)

    required_fields.extend(original_list)

    # Fork (see FORK.md, S30): voters and reactors appear as the public actor.
    vote_item = Case(
        When(
            votes__isnull=False,
            votes__deleted_at__isnull=True,
            then=JSONObject(
                vote=F("votes__vote"),
                actor_details=JSONObject(
                    id=F("votes__actor__id"),
                    avatar_url=Case(
                        When(
                            votes__actor__avatar_asset__isnull=False,
                            then=Concat(
                                Value("/api/assets/v2/static/"),
                                Cast("votes__actor__avatar_asset", CharField()),
                                Value("/"),
                            ),
                        ),
                        default=F("votes__actor__avatar"),
                        output_field=CharField(),
                    ),
                    display_name=F("votes__actor__display_name"),
                    is_bot=F("votes__actor__is_bot"),
                ),
            ),
        ),
        default=None,
        output_field=JSONField(),
    )
    reaction_item = Case(
        When(
            issue_reactions__isnull=False,
            issue_reactions__deleted_at__isnull=True,
            then=JSONObject(
                reaction=F("issue_reactions__reaction"),
                actor_details=JSONObject(
                    id=F("issue_reactions__actor__id"),
                    avatar_url=Case(
                        When(
                            issue_reactions__actor__avatar_asset__isnull=False,
                            then=Concat(
                                Value("/api/assets/v2/static/"),
                                Cast("issue_reactions__actor__avatar_asset", CharField()),
                                Value("/"),
                            ),
                        ),
                        default=F("issue_reactions__actor__avatar"),
                        output_field=CharField(),
                    ),
                    display_name=F("issue_reactions__actor__display_name"),
                    is_bot=F("issue_reactions__actor__is_bot"),
                ),
            ),
        ),
        default=None,
        output_field=JSONField(),
    )
    # Fork: [] rather than null for an item nobody voted on or reacted to.
    issues = issues.annotate(
        vote_items=Coalesce(
            ArrayAgg(
                vote_item, order_by=vote_item,
                filter=Q(votes__isnull=False, votes__deleted_at__isnull=True),
                distinct=True,
            ),
            Value([], output_field=ArrayField(JSONField())),
        ),
        reaction_items=Coalesce(
            ArrayAgg(
                reaction_item, order_by=reaction_item,
                filter=Q(issue_reactions__isnull=False, issue_reactions__deleted_at__isnull=True),
                distinct=True,
            ),
            Value([], output_field=ArrayField(JSONField())),
        ),
    ).values(*required_fields, "vote_items", "reaction_items")

    return issues


def issue_group_values(
    field: str,
    slug: str,
    project_id: Optional[str] = None,
    filters: Dict[str, Any] = {},
    queryset: Optional[QuerySet] = None,
) -> List[Union[str, Any]]:
    # Project-scoped keys only ever come from the board's project.
    if field == "state_id":
        queryset = State.objects.filter(is_triage=False, workspace__slug=slug, project_id=project_id)
        return list(queryset.values_list("id", flat=True))
    if field == "labels__id":
        queryset = Label.objects.filter(workspace__slug=slug, project_id=project_id).values_list("id", flat=True)
        return list(queryset) + ["None"]
    if field == "issue_module__module_id":
        queryset = Module.objects.filter(workspace__slug=slug, project_id=project_id).values_list("id", flat=True)
        return list(queryset) + ["None"]
    if field == "cycle_id":
        queryset = Cycle.objects.filter(workspace__slug=slug, project_id=project_id).values_list("id", flat=True)
        return list(queryset) + ["None"]
    if field == "project_id":
        return list(Project.objects.filter(workspace__slug=slug, id=project_id).values_list("id", flat=True))
    if field == "priority":
        return ["low", "medium", "high", "urgent", "none"]
    if field == "state__group":
        return ["backlog", "unstarted", "started", "completed", "cancelled"]
    if field == "target_date":
        queryset = queryset.values_list("target_date", flat=True).distinct()
        if project_id:
            return list(queryset.filter(project_id=project_id))
        else:
            return list(queryset)
    if field == "start_date":
        queryset = queryset.values_list("start_date", flat=True).distinct()
        if project_id:
            return list(queryset.filter(project_id=project_id))
        else:
            return list(queryset)

    return []
