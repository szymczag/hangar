# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from django.db.models import OuterRef, Subquery

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueCreateSerializer, IssueSerializer
from plane.app.views.base import BaseAPIView
from plane.app.views.issue.base import IssuePaginatedViewSet
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import CycleIssue, FileAsset, Issue, IssueLink, IssueType, Project
from plane.db.models.issue_type import ProjectIssueType
from plane.db.models.state import StateGroup
from plane.utils.host import base_host

from plane.ext.serializers.issue_type import IssueTypeSerializer

EPIC_TYPE_NAME = "Epic"


def project_epic_type(project):
    """The active epic IssueType linked to this project, or None."""
    link = (
        ProjectIssueType.objects.filter(project=project, issue_type__is_epic=True, issue_type__is_active=True)
        .select_related("issue_type")
        .first()
    )
    return link.issue_type if link else None


def epic_queryset(slug, project_id):
    """Epics are issues typed with an epic IssueType.

    Issue.issue_objects excludes epics (see the fork note in IssueManager), so
    epic surfaces query the base soft-delete manager and mirror its other
    exclusions explicitly.
    """
    return (
        Issue.objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            type__is_epic=True,
        )
        .exclude(state__group=StateGroup.TRIAGE.value)
        .exclude(archived_at__isnull=False)
        .exclude(project__archived_at__isnull=False)
        .exclude(is_draft=True)
    )


class EpicSettingsEndpoint(BaseAPIView):
    """Enable/disable epics for a project.

    Enabled == the project has an active epic ProjectIssueType. Disabling
    unlinks the type (soft delete); existing epics are retained.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        return Response({"is_epic_enabled": project_epic_type(project) is not None}, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def patch(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        enable = bool(request.data.get("is_epic_enabled", True))

        if enable:
            epic_type = IssueType.objects.filter(workspace=project.workspace, is_epic=True, is_active=True).first()
            if epic_type is None:
                epic_type = IssueType.objects.create(
                    workspace=project.workspace,
                    name=EPIC_TYPE_NAME,
                    is_epic=True,
                    is_active=True,
                )
            if not ProjectIssueType.objects.filter(project=project, issue_type=epic_type).exists():
                ProjectIssueType.objects.create(project=project, issue_type=epic_type)
        else:
            # Soft delete the link; epics and their data are retained.
            ProjectIssueType.objects.filter(project=project, issue_type__is_epic=True).delete()

        return Response({"is_epic_enabled": enable}, status=status.HTTP_200_OK)


class IssueTypeListEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        issue_types = IssueType.objects.filter(
            workspace__slug=slug,
            project_issue_types__project_id=project_id,
        ).distinct()
        return Response(IssueTypeSerializer(issue_types, many=True).data, status=status.HTTP_200_OK)


class EpicViewSet(BaseAPIView):
    """List/create epics for a project."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        epics = (
            epic_queryset(slug, project_id)
            .select_related("workspace", "project", "state", "parent")
            .prefetch_related("assignees", "labels")
            .annotate(
                sub_issues_count=Count(
                    "parent_issue",
                    filter=Q(parent_issue__deleted_at__isnull=True) & ~Q(parent_issue__type__is_epic=True),
                    distinct=True,
                )
            )
            .order_by("-created_at")
        )
        serializer = IssueSerializer(epics, many=True, fields=self.fields, expand=self.expand)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        epic_type = project_epic_type(project)
        if epic_type is None:
            return Response(
                {"error": "Epics are not enabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = IssueCreateSerializer(
            data=request.data,
            context={
                "project_id": project_id,
                "workspace_id": project.workspace_id,
                "default_assignee_id": project.default_assignee_id,
            },
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # The epic type is never taken from the client — it is fixed to the
        # project's active epic type.
        serializer.save(type=epic_type)

        issue_activity.delay(
            type="issue.activity.created",
            requested_data=json.dumps(self.request.data, cls=DjangoJSONEncoder),
            actor_id=str(request.user.id),
            issue_id=str(serializer.data.get("id", None)),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        epic = epic_queryset(slug, project_id).get(pk=serializer.data["id"])
        return Response(IssueSerializer(epic).data, status=status.HTTP_201_CREATED)


class EpicDetailViewSet(BaseAPIView):
    def get_epic(self, slug, project_id, pk):
        return epic_queryset(slug, project_id).get(pk=pk)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, pk):
        epic = self.get_epic(slug, project_id, pk)
        return Response(IssueSerializer(epic, fields=self.fields, expand=self.expand).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, pk):
        epic = self.get_epic(slug, project_id, pk)
        current_instance = json.dumps(IssueSerializer(epic).data, cls=DjangoJSONEncoder)

        requested_data = {key: value for key, value in request.data.items() if key not in ["type", "type_id"]}
        serializer = IssueCreateSerializer(epic, data=requested_data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()

        issue_activity.delay(
            type="issue.activity.updated",
            requested_data=json.dumps(requested_data, cls=DjangoJSONEncoder),
            actor_id=str(request.user.id),
            issue_id=str(pk),
            project_id=str(project_id),
            current_instance=current_instance,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], creator=True, model=Issue)
    def delete(self, request, slug, project_id, pk):
        epic = self.get_epic(slug, project_id, pk)
        epic.delete()
        issue_activity.delay(
            type="issue.activity.deleted",
            requested_data=json.dumps({"issue_id": str(pk)}),
            actor_id=str(request.user.id),
            issue_id=str(pk),
            project_id=str(project_id),
            current_instance={},
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class EpicPaginatedViewSet(IssuePaginatedViewSet):
    """v2 paginated epic list — the surface the web epic store fetches.

    Mirrors IssuePaginatedViewSet.get_queryset with the epic base queryset
    (issue_objects excludes epics; see the fork note in IssueManager).
    """

    def get_queryset(self):
        queryset = epic_queryset(self.kwargs.get("slug"), self.kwargs.get("project_id"))
        return (
            queryset.select_related("state")
            .annotate(cycle_id=Subquery(CycleIssue.objects.filter(issue=OuterRef("id")).values("cycle_id")[:1]))
            .annotate(
                link_count=Subquery(
                    IssueLink.objects.filter(issue=OuterRef("id"))
                    .values("issue")
                    .annotate(count=Count("id"))
                    .values("count")
                )
            )
            .annotate(
                attachment_count=Subquery(
                    FileAsset.objects.filter(
                        issue_id=OuterRef("id"),
                        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                    )
                    .values("issue_id")
                    .annotate(count=Count("id"))
                    .values("count")
                )
            )
            .annotate(
                sub_issues_count=Subquery(
                    Issue.issue_objects.filter(parent=OuterRef("id"))
                    .values("parent")
                    .annotate(count=Count("id"))
                    .values("count")
                )
            )
        )


class EpicIssuesEndpoint(BaseAPIView):
    """Work items grouped under an epic (children via the parent FK), with
    progress counts."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, pk):
        # Validate the epic within the project scope
        epic_queryset(slug, project_id).get(pk=pk)

        children = Issue.issue_objects.filter(
            workspace__slug=slug, parent_id=pk
        ).select_related("state", "project")
        total = children.count()
        completed = children.filter(state__group=StateGroup.COMPLETED.value).count()
        serializer = IssueSerializer(children, many=True, fields=self.fields, expand=self.expand)
        return Response(
            {
                "issues": serializer.data,
                "progress": {"total_issues": total, "completed_issues": completed},
            },
            status=status.HTTP_200_OK,
        )
