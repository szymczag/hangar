# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.utils import timezone
from django.db import transaction
from django.db.models import BooleanField, OuterRef, F, Value, UUIDField, Subquery, Count, IntegerField
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db.models.functions import Coalesce

# Third Party imports
from rest_framework.response import Response
from rest_framework import serializers, status

# Module imports
from .. import BaseAPIView
from plane.app.serializers import IssueSerializer
from plane.app.permissions import ProjectEntityPermission
from plane.db.models import Issue, IssueLink, FileAsset, CycleIssue, IssueLabel, IssueAssignee, ModuleIssue, Project
from plane.bgtasks.issue_activities_task import issue_activity
from plane.utils.timezone_converter import user_timezone_converter
from collections import defaultdict
from plane.utils.host import base_host
from plane.utils.order_queryset import order_issue_queryset


class SubIssuesEndpoint(BaseAPIView):
    permission_classes = [ProjectEntityPermission]

    @method_decorator(gzip_page)
    def get(self, request, slug, project_id, issue_id):
        get_object_or_404(
            Issue.issue_objects,
            pk=issue_id,
            workspace__slug=slug,
            project_id=project_id,
        )
        sub_issues = (
            Issue.issue_objects.filter(parent_id=issue_id, workspace__slug=slug, project_id=project_id)
            .annotate(
                cycle_id=Subquery(
                    CycleIssue.objects.filter(issue=OuterRef("id"), deleted_at__isnull=True).values("cycle_id")[:1]
                )
            )
            .annotate(
                link_count=Coalesce(
                    Subquery(
                        IssueLink.objects.filter(issue=OuterRef("id"))
                        .order_by()
                        .values("issue")
                        .annotate(count=Count("id"))
                        .values("count"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
            .annotate(
                attachment_count=Coalesce(
                    Subquery(
                        FileAsset.objects.filter(
                            issue_id=OuterRef("id"),
                            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                        )
                        .order_by()
                        .values("issue_id")
                        .annotate(count=Count("id"))
                        .values("count"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
            .annotate(
                sub_issues_count=Coalesce(
                    Subquery(
                        Issue.issue_objects.filter(parent=OuterRef("id"))
                        .order_by()
                        .values("parent")
                        .annotate(count=Count("id"))
                        .values("count"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
            .annotate(
                label_ids=Coalesce(
                    Subquery(
                        IssueLabel.objects.filter(issue_id=OuterRef("id"), deleted_at__isnull=True)
                        .order_by()
                        .values("issue_id")
                        .annotate(arr=ArrayAgg("label_id", distinct=True))
                        .values("arr"),
                        output_field=ArrayField(UUIDField()),
                    ),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
                assignee_ids=Coalesce(
                    Subquery(
                        IssueAssignee.objects.filter(
                            issue_id=OuterRef("id"),
                            assignee__member_project__is_active=True,
                            deleted_at__isnull=True,
                        )
                        .order_by()
                        .values("issue_id")
                        .annotate(arr=ArrayAgg("assignee_id", distinct=True))
                        .values("arr"),
                        output_field=ArrayField(UUIDField()),
                    ),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
                module_ids=Coalesce(
                    Subquery(
                        ModuleIssue.objects.filter(
                            issue_id=OuterRef("id"),
                            module__archived_at__isnull=True,
                            deleted_at__isnull=True,
                        )
                        .order_by()
                        .values("issue_id")
                        .annotate(arr=ArrayAgg("module_id", distinct=True))
                        .values("arr"),
                        output_field=ArrayField(UUIDField()),
                    ),
                    Value([], output_field=ArrayField(UUIDField())),
                ),
            )
            .annotate(state_group=F("state__group"))
            .annotate(is_epic=Coalesce(F("type__is_epic"), Value(False), output_field=BooleanField()))
        )

        # Ordering
        order_by_param = request.GET.get("order_by", "-created_at")
        group_by = request.GET.get("group_by", False)

        if order_by_param:
            sub_issues, order_by_param = order_issue_queryset(sub_issues, order_by_param)

        sub_issues = list(
            sub_issues.values(
                "id",
                "name",
                "state_id",
                "sort_order",
                "completed_at",
                "estimate_point",
                "priority",
                "start_date",
                "target_date",
                "sequence_id",
                "project_id",
                "parent_id",
                "type_id",
                "is_epic",
                "cycle_id",
                "module_ids",
                "label_ids",
                "assignee_ids",
                "sub_issues_count",
                "created_at",
                "updated_at",
                "created_by",
                "updated_by",
                "attachment_count",
                "link_count",
                "is_draft",
                "archived_at",
                "state_group",
            )
        )

        # create's a dict with state group name with their respective issue id's
        result = defaultdict(list)
        for sub_issue in sub_issues:
            result[sub_issue["state_group"]].append(str(sub_issue["id"]))

        datetime_fields = ["created_at", "updated_at"]
        sub_issues = user_timezone_converter(sub_issues, datetime_fields, request.user.user_timezone)
        # Grouping
        if group_by:
            result_dict = defaultdict(list)

            for issue in sub_issues:
                if group_by == "assignees__ids":
                    if issue["assignee_ids"]:
                        assignee_ids = issue["assignee_ids"]
                        for assignee_id in assignee_ids:
                            result_dict[str(assignee_id)].append(issue)
                    elif issue["assignee_ids"] == []:
                        result_dict["None"].append(issue)

                elif group_by:
                    result_dict[str(issue[group_by])].append(issue)

            return Response(
                {"sub_issues": result_dict, "state_distribution": result},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"sub_issues": sub_issues, "state_distribution": result},
            status=status.HTTP_200_OK,
        )

    # Assign multiple sub issues
    @transaction.atomic
    def post(self, request, slug, project_id, issue_id):
        id_list = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
        try:
            sub_issue_ids = id_list.run_validation(request.data.get("sub_issue_ids"))
        except serializers.ValidationError as exc:
            return Response({"sub_issue_ids": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        if len(set(sub_issue_ids)) != len(sub_issue_ids):
            return Response(
                {"sub_issue_ids": "Duplicate work item IDs are not allowed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Serialize hierarchy mutations per project. The exact project scope on
        # both parent and children prevents cross-project IDOR and partial writes.
        get_object_or_404(
            Project.objects.select_for_update(),
            pk=project_id,
            workspace__slug=slug,
        )
        parent_issue = get_object_or_404(
            Issue.objects.select_for_update(),
            pk=issue_id,
            workspace__slug=slug,
            project_id=project_id,
        )
        locked_sub_issue_ids = list(
            Issue.objects.select_for_update()
            .filter(id__in=sub_issue_ids, workspace__slug=slug, project_id=project_id)
            .values_list("id", flat=True)
        )
        if len(locked_sub_issue_ids) != len(sub_issue_ids):
            return Response(
                {"sub_issue_ids": "Every work item must exist in this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sub_issues = list(Issue.objects.filter(id__in=locked_sub_issue_ids).select_related("type"))

        if parent_issue.id in sub_issue_ids:
            return Response(
                {"sub_issue_ids": "A work item cannot be its own parent"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if any(sub_issue.type_id and sub_issue.type.is_epic for sub_issue in sub_issues):
            return Response(
                {"sub_issue_ids": "Epic work items cannot have a parent"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent_by_id = dict(
            Issue.objects.filter(project_id=project_id, workspace__slug=slug).values_list("id", "parent_id")
        )
        for sub_issue in sub_issues:
            ancestor_id = parent_issue.id
            visited = set()
            while ancestor_id is not None:
                if ancestor_id == sub_issue.id:
                    return Response(
                        {"sub_issue_ids": "Parent assignment would create a cycle"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if ancestor_id in visited:
                    return Response(
                        {"sub_issue_ids": "The existing parent hierarchy contains a cycle"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                visited.add(ancestor_id)
                ancestor_id = parent_by_id.get(ancestor_id)

        previous_parents = {sub_issue.id: sub_issue.parent_id for sub_issue in sub_issues}

        for sub_issue in sub_issues:
            sub_issue.parent = parent_issue

        Issue.objects.bulk_update(sub_issues, ["parent"], batch_size=10)

        updated_sub_issues = (
            Issue.issue_objects.filter(
                id__in=sub_issue_ids,
                workspace__slug=slug,
                project_id=project_id,
            )
            .select_related("type")
            .annotate(state_group=F("state__group"))
        )

        # Track the issue
        _ = [
            issue_activity.delay(
                type="issue.activity.updated",
                requested_data=json.dumps({"parent": str(issue_id)}),
                actor_id=str(request.user.id),
                issue_id=str(sub_issue_id),
                project_id=str(project_id),
                current_instance=json.dumps(
                    {"parent": str(previous_parents[sub_issue_id]) if previous_parents[sub_issue_id] else None}
                ),
                epoch=int(timezone.now().timestamp()),
                notification=True,
                origin=base_host(request=request, is_app=True),
            )
            for sub_issue_id in sub_issue_ids
        ]

        # create's a dict with state group name with their respective issue id's
        result = defaultdict(list)
        for sub_issue in updated_sub_issues:
            result[sub_issue.state_group].append(str(sub_issue.id))

        serializer = IssueSerializer(updated_sub_issues, many=True)
        return Response(
            {"sub_issues": serializer.data, "state_distribution": result},
            status=status.HTTP_200_OK,
        )
