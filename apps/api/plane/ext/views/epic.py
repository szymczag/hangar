# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
from uuid import UUID

# Django imports
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q, OuterRef, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import IssueCreateSerializer, IssueSerializer
from plane.app.views import (
    IssueActivityEndpoint,
    IssueAttachmentV2Endpoint,
    IssueCommentViewSet,
    IssueLinkViewSet,
    IssueReactionViewSet,
    IssueSubscriberViewSet,
    WorkItemDescriptionVersionEndpoint,
)
from plane.app.views.base import BaseAPIView
from plane.app.views.issue.base import IssuePaginatedViewSet
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import CycleIssue, FileAsset, Issue, IssueLink, IssueType, Project, Workspace
from plane.db.models.issue_type import ProjectIssueType
from plane.db.models.state import StateGroup
from plane.utils.host import base_host

from plane.ext.models import EpicUserProperty
from plane.ext.serializers.issue_type import EpicSettingsSerializer, EpicUserPropertySerializer

EPIC_TYPE_NAME = "Epic"
MAX_BULK_EPICS = 100
EPIC_IMMUTABLE_FIELDS = {
    "archived_at",
    "deleted_at",
    "is_draft",
    "parent",
    "parent_id",
    "type",
    "type_id",
}


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
        serializer = EpicSettingsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        enable = serializer.validated_data["is_epic_enabled"]

        with transaction.atomic():
            # Serialize epic-type creation across projects in one workspace;
            # IssueType has no uniqueness constraint for the is_epic flag.
            Workspace.objects.select_for_update().get(pk=project.workspace_id)
            if enable:
                epic_type = IssueType.objects.filter(
                    workspace=project.workspace,
                    is_epic=True,
                    is_active=True,
                ).first()
                if epic_type is None:
                    epic_type = IssueType.objects.create(
                        workspace=project.workspace,
                        name=EPIC_TYPE_NAME,
                        is_epic=True,
                        is_active=True,
                    )
                if not ProjectIssueType.objects.filter(
                    project=project,
                    issue_type=epic_type,
                ).exists():
                    ProjectIssueType.objects.create(project=project, issue_type=epic_type)
            else:
                # Soft delete the link; epics and their data are retained.
                ProjectIssueType.objects.filter(
                    project=project,
                    issue_type__is_epic=True,
                ).delete()

        return Response({"is_epic_enabled": enable}, status=status.HTTP_200_OK)


class EpicUserPropertyEndpoint(BaseAPIView):
    """Read and update per-user Epic filters without touching work-item preferences."""

    def get_property(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        epic_property, _ = EpicUserProperty.objects.get_or_create(user=request.user, project=project)
        return epic_property

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        return Response(EpicUserPropertySerializer(self.get_property(request, slug, project_id)).data)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def patch(self, request, slug, project_id):
        serializer = EpicUserPropertySerializer(
            self.get_property(request, slug, project_id),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

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
        serializer.save(
            type=epic_type,
            parent=None,
            is_draft=False,
            archived_at=None,
            deleted_at=None,
        )

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

        requested_data = {key: value for key, value in request.data.items() if key not in EPIC_IMMUTABLE_FIELDS}
        serializer = IssueCreateSerializer(
            epic,
            data=requested_data,
            partial=True,
            context={
                "project_id": project_id,
                "workspace_id": epic.workspace_id,
                "default_assignee_id": epic.project.default_assignee_id,
            },
        )
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


class EpicListEndpoint(BaseAPIView):
    """Bulk fetch epics by id for the web Epic store."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        epic_ids = []
        for raw_id in request.GET.get("issues", "").split(","):
            if not (raw_id := raw_id.strip()):
                continue
            try:
                epic_ids.append(UUID(raw_id))
            except ValueError:
                return Response({"error": "Invalid issue id"}, status=status.HTTP_400_BAD_REQUEST)
        if not epic_ids:
            return Response({"error": "Issues are required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(epic_ids) > MAX_BULK_EPICS:
            return Response(
                {"error": f"A maximum of {MAX_BULK_EPICS} epics can be requested"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        epics = (
            epic_queryset(slug, project_id)
            .filter(pk__in=epic_ids)
            .select_related("workspace", "project", "state", "parent")
            .prefetch_related("assignees", "labels")
        )
        return Response(
            IssueSerializer(epics, many=True, fields=self.fields, expand=self.expand).data,
            status=status.HTTP_200_OK,
        )


class EpicArchiveEndpoint(BaseAPIView):
    """Archive or unarchive a project-scoped epic."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, pk):
        epic = get_object_or_404(epic_queryset(slug, project_id).select_related("state"), pk=pk)
        if epic.state.group not in [StateGroup.COMPLETED.value, StateGroup.CANCELLED.value]:
            return Response(
                {"error": "Can only archive epics in a completed or cancelled state group"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue_activity.delay(
            type="issue.activity.updated",
            requested_data=json.dumps({"archived_at": str(timezone.now().date()), "automation": False}),
            actor_id=str(request.user.id),
            issue_id=str(epic.id),
            project_id=str(project_id),
            current_instance=json.dumps(IssueSerializer(epic).data, cls=DjangoJSONEncoder),
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        epic.archived_at = timezone.now().date()
        epic.save(update_fields=["archived_at"])
        return Response({"archived_at": str(epic.archived_at)}, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, pk):
        epic = get_object_or_404(
            Issue.all_objects.filter(deleted_at__isnull=True),
            workspace__slug=slug,
            project_id=project_id,
            pk=pk,
            type__is_epic=True,
            archived_at__isnull=False,
        )
        issue_activity.delay(
            type="issue.activity.updated",
            requested_data=json.dumps({"archived_at": None}),
            actor_id=str(request.user.id),
            issue_id=str(epic.id),
            project_id=str(project_id),
            current_instance=json.dumps(IssueSerializer(epic).data, cls=DjangoJSONEncoder),
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        epic.archived_at = None
        epic.save(update_fields=["archived_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class EpicIssuesEndpoint(BaseAPIView):
    """Work items grouped under an epic (children via the parent FK), with
    progress counts."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, pk):
        # Validate the epic within the project scope
        epic_queryset(slug, project_id).get(pk=pk)

        children = Issue.issue_objects.filter(
            workspace__slug=slug,
            project_id=project_id,
            parent_id=pk,
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


class EpicResourceScopeMixin:
    """Reject subresource access unless the URL identifies an epic in this project."""

    epic_lookup_kwarg = "issue_id"

    def dispatch(self, request, *args, **kwargs):
        get_object_or_404(
            epic_queryset(kwargs.get("slug"), kwargs.get("project_id")),
            pk=kwargs.get(self.epic_lookup_kwarg),
        )
        return super().dispatch(request, *args, **kwargs)


class EpicActivityEndpoint(EpicResourceScopeMixin, IssueActivityEndpoint):
    pass


class EpicAttachmentV2Endpoint(EpicResourceScopeMixin, IssueAttachmentV2Endpoint):
    pass


class EpicCommentViewSet(EpicResourceScopeMixin, IssueCommentViewSet):
    pass


class EpicLinkViewSet(EpicResourceScopeMixin, IssueLinkViewSet):
    pass


class EpicReactionViewSet(EpicResourceScopeMixin, IssueReactionViewSet):
    pass


class EpicSubscriberViewSet(EpicResourceScopeMixin, IssueSubscriberViewSet):
    pass


class EpicDescriptionVersionEndpoint(EpicResourceScopeMixin, WorkItemDescriptionVersionEndpoint):
    epic_lookup_kwarg = "work_item_id"
