# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, Project, ProjectMember, WorkspaceMember
from plane.utils.host import base_host

from plane.ext.models import IssueWorkLog
from plane.ext.serializers.worklog import IssueWorkLogSerializer


def time_tracking_enabled(slug, project_id):
    return Project.objects.filter(
        workspace__slug=slug, pk=project_id, is_time_tracking_enabled=True
    ).exists()


def can_modify(worklog, user, slug, project_id):
    """The author, a project admin, or a workspace admin may modify an entry."""
    if worklog.logged_by_id == user.id:
        return True
    if ProjectMember.objects.filter(
        workspace__slug=slug,
        project_id=project_id,
        member=user,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists():
        return True
    return WorkspaceMember.objects.filter(
        workspace__slug=slug,
        member=user,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists()


class IssueWorkLogsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def get(self, request, slug, project_id, issue_id):
        if not time_tracking_enabled(slug, project_id):
            return Response({"error": "Time tracking is not enabled"}, status=status.HTTP_400_BAD_REQUEST)
        get_object_or_404(Issue, workspace__slug=slug, project_id=project_id, pk=issue_id)
        worklogs = IssueWorkLog.objects.filter(
            workspace__slug=slug, project_id=project_id, issue_id=issue_id
        ).select_related("logged_by")
        total = worklogs.aggregate(total_duration=Sum("duration"))["total_duration"] or 0
        return Response(
            {
                "worklogs": IssueWorkLogSerializer(worklogs, many=True).data,
                "total_duration": total,
            },
            status=status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        if not time_tracking_enabled(slug, project_id):
            return Response({"error": "Time tracking is not enabled"}, status=status.HTTP_400_BAD_REQUEST)
        # Scope the issue lookup before writing anything.
        issue = get_object_or_404(Issue, workspace__slug=slug, project_id=project_id, pk=issue_id)

        serializer = IssueWorkLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # logged_by is never client-supplied.
        worklog = serializer.save(
            issue=issue,
            project_id=project_id,
            workspace=issue.workspace,
            logged_by=request.user,
        )
        issue_activity.delay(
            type="worklog.activity.created",
            requested_data=json.dumps({"duration": worklog.duration}, cls=DjangoJSONEncoder),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(IssueWorkLogSerializer(worklog).data, status=status.HTTP_201_CREATED)


class IssueWorkLogDetailEndpoint(BaseAPIView):
    def get_worklog(self, slug, project_id, issue_id, pk):
        return get_object_or_404(
            IssueWorkLog,
            workspace__slug=slug, project_id=project_id, issue_id=issue_id, pk=pk
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def patch(self, request, slug, project_id, issue_id, pk):
        if not time_tracking_enabled(slug, project_id):
            return Response({"error": "Time tracking is not enabled"}, status=status.HTTP_400_BAD_REQUEST)
        worklog = self.get_worklog(slug, project_id, issue_id, pk)
        if not can_modify(worklog, request.user, slug, project_id):
            return Response(
                {"error": "Only the author or a project admin can edit this entry"},
                status=status.HTTP_403_FORBIDDEN,
            )
        current_instance = json.dumps(IssueWorkLogSerializer(worklog).data, cls=DjangoJSONEncoder)
        serializer = IssueWorkLogSerializer(worklog, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        worklog = serializer.save()
        issue_activity.delay(
            type="worklog.activity.updated",
            requested_data=json.dumps({"duration": worklog.duration}, cls=DjangoJSONEncoder),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=current_instance,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def delete(self, request, slug, project_id, issue_id, pk):
        if not time_tracking_enabled(slug, project_id):
            return Response({"error": "Time tracking is not enabled"}, status=status.HTTP_400_BAD_REQUEST)
        worklog = self.get_worklog(slug, project_id, issue_id, pk)
        if not can_modify(worklog, request.user, slug, project_id):
            return Response(
                {"error": "Only the author or a project admin can delete this entry"},
                status=status.HTTP_403_FORBIDDEN,
            )
        duration = worklog.duration
        worklog.delete()
        issue_activity.delay(
            type="worklog.activity.deleted",
            requested_data=json.dumps({"duration": duration}, cls=DjangoJSONEncoder),
            actor_id=str(request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
