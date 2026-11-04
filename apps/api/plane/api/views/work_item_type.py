# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work item types on the external API.

Plane's SDK and MCP server ask for these at `/api/v1/.../work-item-types/`
with an `X-Api-Key` header. The session catalogue stays at `issue-types` under
`/api/`; this module serves the same rows to a token client.
"""

from uuid import UUID

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response

from plane.api.views.base import BaseAPIView
from plane.db.models import Issue, IssueType, Project, ProjectMember, Workspace, WorkspaceMember
from plane.db.models.issue_type import ProjectIssueType
from plane.db.models.project import ROLE
from plane.ext.serializers.issue_type import IssueTypeSerializer
from plane.ext.services import ensure_project_system_types
from plane.ext.views.issue_type import project_issue_types

MAX_IMPORT = 100


def _project_members(user, slug, project_id):
    return ProjectMember.objects.filter(
        workspace__slug=slug,
        member=user,
        project_id=project_id,
        is_active=True,
    )


def _workspace_members(user, slug):
    return WorkspaceMember.objects.filter(
        workspace__slug=slug,
        member=user,
        is_active=True,
    )


class ProjectWorkItemTypePermission(BasePermission):
    """Any project role may read. Writes stay with a project admin.

    A workspace admin who is also a member of the project may write, matching
    `@allow_permission` on the session issue-type views.
    """

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        membership = _project_members(request.user, view.workspace_slug, view.project_id)
        if request.method in SAFE_METHODS:
            return membership.exists()
        if membership.filter(role=ROLE.ADMIN.value).exists():
            return True
        return membership.exists() and _workspace_members(request.user, view.workspace_slug).filter(
            role=ROLE.ADMIN.value
        ).exists()


class WorkspaceWorkItemTypePermission(BasePermission):
    """Any workspace member may read. Creating a workspace type is an admin act."""

    def has_permission(self, request, view):
        if request.user.is_anonymous:
            return False
        membership = _workspace_members(request.user, view.workspace_slug)
        if request.method in SAFE_METHODS:
            return membership.exists()
        return membership.filter(role=ROLE.ADMIN.value).exists()


def _whole_level(value):
    """The SDK types `level` as an int and rejects `1.0`."""
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def _visible_project_ids(user, slug):
    return set(
        ProjectMember.objects.filter(
            member=user,
            is_active=True,
            workspace__slug=slug,
        ).values_list("project_id", flat=True)
    )


def _project_ids_for(issue_type, allowed):
    return [
        str(link.project_id)
        for link in issue_type.project_issue_types.all()
        if link.deleted_at is None and link.project_id in allowed
    ]


def _represent(issue_type, *, level, is_default, project_ids):
    data = IssueTypeSerializer(issue_type).data
    data["id"] = str(issue_type.id)
    data["level"] = _whole_level(level)
    data["is_default"] = is_default
    data["project_ids"] = project_ids
    if data.get("workspace") is not None:
        data["workspace"] = str(data["workspace"])
    return data


def _represent_for_project(issue_type, project_id, allowed):
    link = next(
        (
            item
            for item in issue_type.project_issue_types.all()
            if item.deleted_at is None and item.project_id == project_id
        ),
        None,
    )
    level = link.level if link is not None else issue_type.level
    is_default = link.is_default if link is not None else issue_type.is_default
    return _represent(
        issue_type,
        level=level,
        is_default=is_default,
        project_ids=_project_ids_for(issue_type, allowed),
    )


def _with_links(queryset):
    return queryset.prefetch_related("project_issue_types").order_by("-is_epic", "name")


def _listed_project_types(slug, project_id):
    """Types linked to the project, provisioning Task and Epic when they are missing."""
    types = project_issue_types(slug, project_id)
    if not types.filter(system_key=IssueType.SystemKey.EPIC).exists():
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        ensure_project_system_types(project)
        types = project_issue_types(slug, project_id)
    return types


def _workspace_types(slug):
    return IssueType.objects.filter(workspace__slug=slug)


def _save_type(serializer, issue_type):
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if issue_type is not None and issue_type.system_key and serializer.validated_data.get("is_active") is False:
        return Response(
            {"is_active": "System work item types cannot be deactivated"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    saved = serializer.save()
    return saved


class ProjectWorkItemTypeListCreateAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectWorkItemTypePermission]

    def get(self, request, slug, project_id):
        allowed = _visible_project_ids(request.user, slug)
        issue_types = _with_links(_listed_project_types(slug, project_id))
        project_uuid = UUID(str(project_id))
        return Response(
            [_represent_for_project(issue_type, project_uuid, allowed) for issue_type in issue_types],
            status=status.HTTP_200_OK,
        )

    def post(self, request, slug, project_id):
        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        ensure_project_system_types(project)
        serializer = IssueTypeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # Same rule as the session catalogue: callers cannot mint an Epic.
        issue_type = serializer.save(workspace=project.workspace, is_epic=False)
        ProjectIssueType.objects.create(project=project, issue_type=issue_type, level=0, is_default=False)
        issue_type = _with_links(project_issue_types(slug, project_id).filter(pk=issue_type.pk)).get()
        allowed = _visible_project_ids(request.user, slug)
        return Response(
            _represent_for_project(issue_type, project.id, allowed),
            status=status.HTTP_201_CREATED,
        )


class ProjectWorkItemTypeDetailAPIEndpoint(BaseAPIView):
    permission_classes = [ProjectWorkItemTypePermission]

    def _get_type(self, slug, project_id, type_id):
        return _with_links(project_issue_types(slug, project_id).filter(pk=type_id)).get()

    def get(self, request, slug, project_id, type_id):
        issue_type = self._get_type(slug, project_id, type_id)
        allowed = _visible_project_ids(request.user, slug)
        return Response(
            _represent_for_project(issue_type, UUID(str(project_id)), allowed),
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, project_id, type_id):
        issue_type = self._get_type(slug, project_id, type_id)
        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        saved = _save_type(serializer, issue_type)
        if isinstance(saved, Response):
            return saved
        saved = self._get_type(slug, project_id, type_id)
        allowed = _visible_project_ids(request.user, slug)
        return Response(
            _represent_for_project(saved, UUID(str(project_id)), allowed),
            status=status.HTTP_200_OK,
        )

    def delete(self, request, slug, project_id, type_id):
        issue_type = self._get_type(slug, project_id, type_id)
        refusal = _delete_type(issue_type)
        if refusal is not None:
            return refusal
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceWorkItemTypeListCreateAPIEndpoint(BaseAPIView):
    permission_classes = [WorkspaceWorkItemTypePermission]

    def get(self, request, slug):
        allowed = _visible_project_ids(request.user, slug)
        issue_types = _with_links(_workspace_types(slug))
        return Response(
            [
                _represent(
                    issue_type,
                    level=issue_type.level,
                    is_default=issue_type.is_default,
                    project_ids=_project_ids_for(issue_type, allowed),
                )
                for issue_type in issue_types
            ],
            status=status.HTTP_200_OK,
        )

    def post(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = IssueTypeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        issue_type = serializer.save(workspace=workspace, is_epic=False)
        issue_type = _with_links(_workspace_types(slug).filter(pk=issue_type.pk)).get()
        return Response(
            _represent(issue_type, level=issue_type.level, is_default=issue_type.is_default, project_ids=[]),
            status=status.HTTP_201_CREATED,
        )


class WorkspaceWorkItemTypeDetailAPIEndpoint(BaseAPIView):
    permission_classes = [WorkspaceWorkItemTypePermission]

    def _get_type(self, slug, type_id):
        return _with_links(_workspace_types(slug).filter(pk=type_id)).get()

    def get(self, request, slug, type_id):
        issue_type = self._get_type(slug, type_id)
        allowed = _visible_project_ids(request.user, slug)
        return Response(
            _represent(
                issue_type,
                level=issue_type.level,
                is_default=issue_type.is_default,
                project_ids=_project_ids_for(issue_type, allowed),
            ),
            status=status.HTTP_200_OK,
        )

    def patch(self, request, slug, type_id):
        issue_type = self._get_type(slug, type_id)
        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        saved = _save_type(serializer, issue_type)
        if isinstance(saved, Response):
            return saved
        saved = self._get_type(slug, type_id)
        allowed = _visible_project_ids(request.user, slug)
        return Response(
            _represent(
                saved,
                level=saved.level,
                is_default=saved.is_default,
                project_ids=_project_ids_for(saved, allowed),
            ),
            status=status.HTTP_200_OK,
        )

    def delete(self, request, slug, type_id):
        issue_type = self._get_type(slug, type_id)
        refusal = _delete_type(issue_type)
        if refusal is not None:
            return refusal
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImportWorkItemTypesAPIEndpoint(BaseAPIView):
    """Link workspace types onto a project. The SDK posts `{work_item_types: [id]}`."""

    permission_classes = [ProjectWorkItemTypePermission]

    def post(self, request, slug, project_id):
        raw_ids = request.data.get("work_item_types")
        if not isinstance(raw_ids, list):
            return Response(
                {"work_item_types": "Expected a list of work item type ids."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > MAX_IMPORT:
            return Response(
                {"work_item_types": f"At most {MAX_IMPORT} types can be imported at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            type_ids = list(dict.fromkeys(UUID(str(value)) for value in raw_ids))
        except (TypeError, ValueError):
            return Response(
                {"work_item_types": "Expected a list of work item type ids."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = Project.objects.get(workspace__slug=slug, pk=project_id)
        found = {issue_type.id: issue_type for issue_type in IssueType.objects.filter(workspace__slug=slug, pk__in=type_ids)}
        if len(found) != len(type_ids):
            return Response(
                {"work_item_types": "One or more types do not belong to this workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if any(not issue_type.is_active for issue_type in found.values()):
            return Response(
                {"work_item_types": "Work item type is not active for this project."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for type_id in type_ids:
                issue_type = found[type_id]
                ProjectIssueType.objects.get_or_create(
                    project=project,
                    issue_type=issue_type,
                    defaults={"level": 1 if issue_type.is_epic else 0, "is_default": False},
                )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _delete_type(issue_type):
    if issue_type.system_key:
        return Response(
            {"error": "System work item types cannot be deleted"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if Issue.objects.filter(type=issue_type).exists():
        return Response(
            {"error": "This type is in use — deactivate it instead"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    issue_type.delete()
    return None
