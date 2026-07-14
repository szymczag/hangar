# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from datetime import datetime, timedelta
import hmac

import jwt

# Django imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

# Third party modules
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Module imports
from plane.app.permissions import WorkSpaceAdminPermission
from plane.app.serializers import (
    WorkSpaceMemberInviteSerializer,
    WorkSpaceMemberInvitePublicSerializer,
    WorkSpaceMemberSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.bgtasks.event_tracking_task import track_event
from plane.bgtasks.workspace_invitation_task import workspace_invitation
from plane.db.models import Profile, Workspace, WorkspaceMember, WorkspaceMemberInvite
from plane.utils.cache import invalidate_cache, invalidate_cache_directly
from plane.utils.host import base_host
from plane.utils.analytics_events import USER_JOINED_WORKSPACE, USER_INVITED_TO_WORKSPACE
from .. import BaseViewSet


class WorkspaceInvitationsViewset(BaseViewSet):
    """Endpoint for creating, listing and  deleting workspaces"""

    serializer_class = WorkSpaceMemberInviteSerializer
    model = WorkspaceMemberInvite

    permission_classes = [WorkSpaceAdminPermission]

    def get_queryset(self):
        return self.filter_queryset(
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .select_related("workspace", "workspace__owner", "created_by")
        )

    def create(self, request, slug):
        emails = request.data.get("emails", [])
        # Check if email is provided
        if not emails:
            return Response({"error": "Emails are required"}, status=status.HTTP_400_BAD_REQUEST)

        # check for role level of the requesting user
        requesting_user = WorkspaceMember.objects.get(workspace__slug=slug, member=request.user, is_active=True)

        # Check if any invited user has an higher role
        if len([email for email in emails if int(email.get("role", 5)) > requesting_user.role]):
            return Response(
                {"error": "You cannot invite a user with higher role"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the workspace object
        workspace = Workspace.objects.get(slug=slug)

        # Check if user is already a member of workspace
        workspace_members = WorkspaceMember.objects.filter(
            workspace_id=workspace.id,
            member__email__in=[email.get("email") for email in emails],
            is_active=True,
        ).select_related("member", "member__avatar_asset")

        if workspace_members:
            return Response(
                {
                    "error": "Some users are already member of workspace",
                    "workspace_users": WorkSpaceMemberSerializer(workspace_members, many=True).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace_invitations = []
        for email in emails:
            try:
                validate_email(email.get("email"))
                workspace_invitations.append(
                    WorkspaceMemberInvite(
                        email=email.get("email").strip().lower(),
                        workspace_id=workspace.id,
                        token=jwt.encode(
                            {"email": email, "timestamp": datetime.now().timestamp()},
                            settings.SECRET_KEY,
                            algorithm="HS256",
                        ),
                        role=email.get("role", 5),
                        expires_at=timezone.now() + timedelta(days=7),
                        created_by=request.user,
                    )
                )
            except ValidationError:
                return Response(
                    {
                        "error": f"Invalid email - {email} provided a valid email address is required to send the invite"  # noqa: E501
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # Create workspace member invite
        workspace_invitations = WorkspaceMemberInvite.objects.bulk_create(
            workspace_invitations, batch_size=10, ignore_conflicts=True
        )

        current_site = base_host(request=request, is_app=True)

        # Send invitations
        for invitation in workspace_invitations:
            workspace_invitation.delay(
                invitation.email,
                workspace.id,
                invitation.token,
                current_site,
                request.user.email,
            )
            track_event.delay(
                user_id=request.user.id,
                event_name=USER_INVITED_TO_WORKSPACE,
                slug=slug,
                event_properties={
                    "user_id": request.user.id,
                    "workspace_id": workspace.id,
                    "workspace_slug": workspace.slug,
                    "invitee_role": invitation.role,
                    "invited_at": str(timezone.now()),
                    "invitee_email": invitation.email,
                },
            )

        return Response({"message": "Emails sent successfully"}, status=status.HTTP_200_OK)

    def destroy(self, request, slug, pk):
        workspace_member_invite = WorkspaceMemberInvite.objects.get(pk=pk, workspace__slug=slug)
        workspace_member_invite.revoked_at = timezone.now()
        workspace_member_invite.save(update_fields=["revoked_at", "updated_at"])
        workspace_member_invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceJoinEndpoint(BaseAPIView):
    permission_classes = [AllowAny]
    """Invitation response endpoint the user can respond to the invitation"""

    @invalidate_cache(path="/api/workspaces/", user=False)
    @invalidate_cache(path="/api/users/me/workspaces/", multiple=True)
    @invalidate_cache(
        path="/api/workspaces/:slug/members/",
        user=False,
        multiple=True,
        url_params=True,
    )
    @invalidate_cache(path="/api/users/me/settings/", multiple=True)
    def post(self, request, slug, pk):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required to accept workspace invitation"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        now = timezone.now()
        accepted = request.data.get("accepted") is True
        with transaction.atomic():
            workspace_invite = WorkspaceMemberInvite.objects.select_for_update().get(
                pk=pk,
                workspace__slug=slug,
            )
            token = str(request.data.get("token", ""))
            if not token or not hmac.compare_digest(workspace_invite.token, token):
                return Response(
                    {"error": "You do not have permission to join the workspace"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if request.user.email.casefold() != workspace_invite.email.casefold():
                return Response(
                    {"error": "You do not have permission to accept this invitation"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if (
                workspace_invite.responded_at is not None
                or workspace_invite.revoked_at is not None
                or workspace_invite.consumed_at is not None
                or workspace_invite.expires_at is None
                or workspace_invite.expires_at <= now
            ):
                return Response(
                    {"error": "This invitation is no longer active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            workspace_invite.accepted = accepted
            workspace_invite.responded_at = now
            if not accepted:
                workspace_invite.revoked_at = now
                workspace_invite.save(update_fields=["accepted", "responded_at", "revoked_at", "updated_at"])
                return Response(
                    {"message": "Workspace Invitation was not accepted"},
                    status=status.HTTP_200_OK,
                )

            workspace_member = WorkspaceMember.objects.filter(
                workspace=workspace_invite.workspace,
                member=request.user,
            ).first()
            if workspace_member is not None:
                workspace_member.is_active = True
                workspace_member.role = workspace_invite.role
                workspace_member.save(update_fields=["is_active", "role", "updated_at"])
            else:
                WorkspaceMember.objects.create(
                    workspace=workspace_invite.workspace,
                    member=request.user,
                    role=workspace_invite.role,
                )

            Profile.objects.update_or_create(
                user=request.user,
                defaults={"last_workspace_id": workspace_invite.workspace.id},
            )
            workspace_invite.consumed_at = now
            workspace_invite.deleted_at = now
            workspace_invite.save(update_fields=["accepted", "responded_at", "consumed_at", "deleted_at", "updated_at"])

            event_kwargs = {
                "user_id": request.user.id,
                "event_name": USER_JOINED_WORKSPACE,
                "slug": slug,
                "event_properties": {
                    "user_id": request.user.id,
                    "workspace_id": workspace_invite.workspace.id,
                    "workspace_slug": workspace_invite.workspace.slug,
                    "role": workspace_invite.role,
                    "joined_at": str(now),
                },
            }
            transaction.on_commit(lambda: track_event.delay(**event_kwargs))

        return Response(
            {"message": "Workspace Invitation Accepted"},
            status=status.HTTP_200_OK,
        )

    def get(self, request, slug, pk):
        workspace_invitation = WorkspaceMemberInvite.objects.get(workspace__slug=slug, pk=pk)
        # Use the public serializer that omits the token and invite_link fields so
        # that an unauthenticated caller cannot retrieve the acceptance token
        # (GHSA-86mg-259g-pwgg / GHSA-gf48-p6jp-cwc4).
        serializer = WorkSpaceMemberInvitePublicSerializer(workspace_invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserWorkspaceInvitationsViewSet(BaseViewSet):
    serializer_class = WorkSpaceMemberInviteSerializer
    model = WorkspaceMemberInvite

    def get_queryset(self):
        return self.filter_queryset(
            super().get_queryset().filter(email=self.request.user.email).select_related("workspace")
        )

    @invalidate_cache(path="/api/workspaces/", user=False)
    @invalidate_cache(path="/api/users/me/workspaces/", multiple=True)
    def create(self, request):
        invitations = request.data.get("invitations", [])
        if not invitations:
            return Response({"error": "Invitations are required"}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        with transaction.atomic():
            workspace_invitations = list(
                WorkspaceMemberInvite.objects.select_for_update()
                .filter(
                    pk__in=invitations,
                    email__iexact=request.user.email,
                    responded_at__isnull=True,
                    revoked_at__isnull=True,
                    consumed_at__isnull=True,
                    deleted_at__isnull=True,
                    expires_at__gt=now,
                )
                .select_related("workspace")
                .order_by("-created_at")
            )
            if len(workspace_invitations) != len(set(invitations)):
                return Response(
                    {"error": "One or more invitations are no longer active"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for invitation in workspace_invitations:
                WorkspaceMember.objects.update_or_create(
                    workspace_id=invitation.workspace_id,
                    member=request.user,
                    defaults={"is_active": True, "role": invitation.role},
                )
                cache_kwargs = {
                    "path": f"/api/workspaces/{invitation.workspace.slug}/members/",
                    "user": False,
                    "request": request,
                    "multiple": True,
                }
                event_kwargs = {
                    "user_id": request.user.id,
                    "event_name": USER_JOINED_WORKSPACE,
                    "slug": invitation.workspace.slug,
                    "event_properties": {
                        "user_id": request.user.id,
                        "workspace_id": invitation.workspace.id,
                        "workspace_slug": invitation.workspace.slug,
                        "role": invitation.role,
                        "joined_at": str(now),
                    },
                }
                transaction.on_commit(lambda kwargs=cache_kwargs: invalidate_cache_directly(**kwargs))
                transaction.on_commit(lambda kwargs=event_kwargs: track_event.delay(**kwargs))

            WorkspaceMemberInvite.objects.filter(pk__in=[invite.pk for invite in workspace_invitations]).update(
                accepted=True,
                responded_at=now,
                consumed_at=now,
                deleted_at=now,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
