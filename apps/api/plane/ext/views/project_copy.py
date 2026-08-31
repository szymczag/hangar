# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import logging

# Django imports
from django.db.models import Exists, OuterRef, Prefetch, Subquery

# Third party imports
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import ProjectListSerializer
from plane.app.views.base import BaseAPIView
from plane.bgtasks.webhook_task import model_activity
from plane.db.models import (
    DeployBoard,
    Project,
    ProjectMember,
    ProjectUserProperty,
    UserFavorite,
    WorkspaceMember,
)
from plane.ext.serializers.project_copy import ProjectDuplicateSerializer
from plane.ext.services.project_copy import ProjectCopyError, duplicate_project
from plane.utils.host import base_host

log = logging.getLogger(__name__)


def _project_list_queryset(user, slug):
    """The annotations ``ProjectListSerializer`` reads.

    Mirrors ``ProjectViewSet.get_queryset`` so the duplicate response has the
    same shape as the one ``create`` returns, and the web store can treat the two
    identically. Serializing a bare ``Project`` instead raises, because
    ``is_favorite``/``member_role``/``anchor``/``sort_order`` are declared
    read-only fields with no model counterpart.
    """
    sort_order = ProjectUserProperty.objects.filter(user=user, project_id=OuterRef("pk"), workspace__slug=slug).values(
        "sort_order"
    )

    return (
        Project.objects.filter(workspace__slug=slug)
        .select_related("workspace", "workspace__owner", "default_assignee", "project_lead")
        .annotate(
            is_favorite=Exists(
                UserFavorite.objects.filter(
                    user=user,
                    entity_identifier=OuterRef("pk"),
                    entity_type="project",
                    project_id=OuterRef("pk"),
                )
            )
        )
        .annotate(
            member_role=ProjectMember.objects.filter(
                project_id=OuterRef("pk"), member_id=user.id, is_active=True
            ).values("role")
        )
        .annotate(
            anchor=DeployBoard.objects.filter(
                entity_name="project", entity_identifier=OuterRef("pk"), workspace__slug=slug
            ).values("anchor")
        )
        .annotate(sort_order=Subquery(sort_order))
        .prefetch_related(
            Prefetch(
                "project_projectmember",
                queryset=ProjectMember.objects.filter(workspace__slug=slug, is_active=True).select_related("member"),
                to_attr="members_list",
            )
        )
    )


class ProjectDuplicateUserThrottle(SimpleRateThrottle):
    scope = "project_duplicate_user"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class ProjectDuplicateWorkspaceThrottle(SimpleRateThrottle):
    """Per-workspace, because the cost lands on the workspace row's lock.

    One user staying under their own limit can still stall project creation for
    everyone else in the workspace, so the two throttles are not redundant.
    """

    scope = "project_duplicate_workspace"

    def get_cache_key(self, request, view):
        slug = view.kwargs.get("slug")
        if not slug:
            return None
        return self.cache_format % {"scope": self.scope, "ident": slug}


class ProjectDuplicateEndpoint(BaseAPIView):
    """Copy a project's configuration into a new project.

    The source project id is carried in the URL rather than the body on purpose:
    ``allow_permission`` resolves its subject from ``kwargs["project_id"]``, so a
    body-supplied source would leave this endpoint with no project-level check
    at all while it reads the source's entire object graph.
    """

    throttle_classes = [ProjectDuplicateUserThrottle, ProjectDuplicateWorkspaceThrottle]

    # ADMIN of the source, not MEMBER. The copy re-links the source's custom
    # work item types (`_copy_work_item_types`), and `IssueTypeDetailEndpoint`
    # authorizes a mutation by ADMIN of *any* project linking the type. Since
    # the caller becomes ADMIN of the copy, allowing a mere MEMBER to duplicate
    # would hand them admin control over type and property definitions shared
    # with projects they do not administer -- and may not even belong to.
    @allow_permission([ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        # `allow_permission` at PROJECT level proves the caller is an active
        # member of the *source*, which is what stops a workspace member reading
        # a project whose network is SECRET. It says nothing about whether they
        # may create a project, which `ProjectViewSet.create` gates separately at
        # workspace level -- so check that too. The two are independent.
        if not WorkspaceMember.objects.filter(
            member=request.user,
            workspace__slug=slug,
            role__in=[ROLE.ADMIN.value, ROLE.MEMBER.value],
            is_active=True,
        ).exists():
            return Response(
                {"error": "You don't have the required permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        source = Project.objects.filter(pk=project_id, workspace__slug=slug).first()
        if source is None:
            return Response({"error": "Project does not exist"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProjectDuplicateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        payload = serializer.validated_data

        try:
            result = duplicate_project(
                source=source,
                actor=request.user,
                name=payload.get("name"),
                identifier=payload.get("identifier"),
                network=payload.get("network"),
                options=payload.get("include"),
            )
        except ProjectCopyError as error:
            body = {"error": error.code}
            if error.detail is not None:
                body["detail"] = error.detail
            return Response(body, status=error.status_code)

        model_activity.delay(
            model_name="project",
            model_id=str(result.project.id),
            requested_data=request.data,
            current_instance=None,
            actor_id=request.user.id,
            slug=slug,
            origin=base_host(request=request, is_app=True),
        )

        created = _project_list_queryset(request.user, slug).filter(pk=result.project.id).first()
        data = ProjectListSerializer(created).data
        data["copy_summary"] = {
            "source_project_id": str(source.id),
            "counts": result.counts,
            "skipped": result.skipped,
        }
        return Response(data, status=status.HTTP_201_CREATED)
