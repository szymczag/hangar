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
from plane.bgtasks.project_add_user_email_task import project_add_user_email
from plane.bgtasks.webhook_task import model_activity
from plane.db.models import (
    DeployBoard,
    FileAsset,
    Project,
    ProjectMember,
    ProjectUserProperty,
    UserFavorite,
    WorkspaceMember,
)
from plane.ext.models import ProjectCopyJob
from plane.ext.models.project_copy_job import ACTIVE_STATUSES
from plane.ext.serializers.project_copy import ProjectCopyJobSerializer, ProjectDuplicateSerializer
from plane.ext.services.project_copy import ProjectCopyError, duplicate_project
from plane.ext.tasks import copy_project_work_items
from plane.settings.storage import S3Storage
from plane.utils.file_asset_copy import AssetCopyError, copyable_asset, duplicate_file_asset
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


def _copy_cover_image(request, source_asset_id, target):
    """Copy the source project's cover into the new project.

    Runs after the copy transaction has committed, because an S3 object copy
    cannot be rolled back with it. A cover that cannot be copied is not worth
    failing a project over, so this degrades to no cover and says so.
    """
    if source_asset_id is None:
        return None

    original = copyable_asset(asset_id=source_asset_id, workspace=target.workspace, actor_id=request.user.id)
    if original is None:
        return "cover_image:unreadable"

    try:
        duplicated = duplicate_file_asset(
            storage=S3Storage(request=request),
            original_asset=original,
            workspace=target.workspace,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
            entity_fields={},
            project_id=target.id,
            actor_id=request.user.id,
        )
    except AssetCopyError:
        log.warning("Could not copy the cover image for project %s", target.id, exc_info=True)
        return "cover_image:failed"

    Project.objects.filter(pk=target.pk).update(cover_image_asset=duplicated)
    return None


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

        # One work item copy per workspace at a time. The row caps bound a single
        # copy; this is what stops one person queueing ten large ones and holding
        # a worker for an hour. Only checked when work items were asked for --
        # a configuration copy is bounded and cheap.
        if (payload.get("include") or {}).get("work_items") and ProjectCopyJob.objects.filter(
            workspace__slug=slug, status__in=ACTIVE_STATUSES
        ).exists():
            return Response(
                {"error": "PROJECT_COPY_ALREADY_RUNNING"},
                status=status.HTTP_409_CONFLICT,
            )

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

        # Everything from here runs after `duplicate_project` has committed, so
        # the project exists whatever happens next. Reporting a failure now
        # would tell the caller the copy did not happen when it did, and leave
        # them to discover the project by accident -- so each side effect is
        # allowed to fail on its own and is reported in `copy_summary.skipped`.
        cover_note = _copy_cover_image(request, result.cover_source_asset_id, result.project)
        if cover_note:
            result.skipped.append(cover_note)

        # Tell the people the copy enrolled, the same way `ProjectMemberViewSet`
        # does. Nobody is mailed about a project that rolled back, because there
        # is no longer any way for it to.
        for member_id in result.notify_member_ids:
            try:
                project_add_user_email.delay(
                    base_host(request=request, is_app=True),
                    member_id,
                    request.user.id,
                )
            except Exception:
                log.warning("Could not queue the project-added email for %s", member_id, exc_info=True)
                result.skipped.append("members:not-notified")
                break

        try:
            model_activity.delay(
                model_name="project",
                model_id=str(result.project.id),
                requested_data=request.data,
                current_instance=None,
                actor_id=request.user.id,
                slug=slug,
                origin=base_host(request=request, is_app=True),
            )
        except Exception:
            log.warning("Could not queue the creation activity for project %s", result.project.id, exc_info=True)

        # Dispatched here rather than inside the service, for the same reason the
        # cover image is: the job reads rows that only exist once the transaction
        # has committed. A broker failure is not fatal -- the job row is already
        # queued, and `reclaim_stalled_project_copies` picks up anything that was
        # never delivered.
        if result.work_item_job_id is not None:
            try:
                copy_project_work_items.delay(str(result.work_item_job_id))
            except Exception:
                log.warning(
                    "Could not queue the work item copy for project %s; the sweeper will retry",
                    result.project.id,
                    exc_info=True,
                )

        created = _project_list_queryset(request.user, slug).filter(pk=result.project.id).first()
        data = ProjectListSerializer(created).data
        data["copy_summary"] = {
            "source_project_id": str(source.id),
            "counts": result.counts,
            "skipped": result.skipped,
        }
        if result.work_item_job_id is not None:
            data["copy_summary"]["work_items"] = {
                "job_id": str(result.work_item_job_id),
                "status": ProjectCopyJob.Status.QUEUED,
                "total": result.counts.get("work_items_planned", 0),
                "copied": 0,
            }
        return Response(data, status=status.HTTP_201_CREATED)


class ProjectCopyStatusEndpoint(BaseAPIView):
    """How far the work item copy of this project has got.

    Keyed on the *target* project rather than the job id, because that is what
    the client has: the duplicate form navigates straight to the copy, and a page
    reload loses any id held in memory. It also means the read is authorised
    exactly like every other project read, with no new surface.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def get(self, request, slug, project_id):
        job = ProjectCopyJob.objects.filter(target_project_id=project_id, workspace__slug=slug).first()
        if job is None:
            # Most projects were never copied; that is not an error.
            return Response({"job": None}, status=status.HTTP_200_OK)
        return Response({"job": ProjectCopyJobSerializer(job).data}, status=status.HTTP_200_OK)


class ProjectCopyRetryEndpoint(BaseAPIView):
    """Ask a failed copy to carry on from where it stopped.

    Resuming is safe because every phase skips the work item numbers already
    present, so a retry adds what is missing rather than a second copy of what
    is not. Only a failed job can be retried; a running one already has a worker,
    and the sweeper covers one whose worker died.
    """

    @allow_permission([ROLE.ADMIN], level="PROJECT")
    def post(self, request, slug, project_id):
        job = ProjectCopyJob.objects.filter(target_project_id=project_id, workspace__slug=slug).first()
        if job is None:
            return Response({"error": "No copy has been run for this project."}, status=status.HTTP_404_NOT_FOUND)
        if job.status != ProjectCopyJob.Status.FAILED:
            return Response({"error": "PROJECT_COPY_NOT_RETRYABLE"}, status=status.HTTP_409_CONFLICT)

        job.status = ProjectCopyJob.Status.QUEUED
        job.reason = ""
        job.completed_at = None
        job.attempt_count = 0
        job.save(update_fields=["status", "reason", "completed_at", "attempt_count", "updated_at"])

        try:
            copy_project_work_items.delay(str(job.id))
        except Exception:
            log.warning("Could not queue the retry for copy job %s; the sweeper will retry", job.id, exc_info=True)

        return Response({"job": ProjectCopyJobSerializer(job).data}, status=status.HTTP_200_OK)
