# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import transaction
from django.utils import timezone

# Module imports
from plane.db.models import (
    ProjectMember,
    ProjectMemberInvite,
    WorkspaceMember,
)
from plane.utils.cache import invalidate_cache_directly
from plane.bgtasks.event_tracking_task import track_event
from plane.utils.analytics_events import USER_JOINED_WORKSPACE
from plane.authentication.services.invitations import accepted_membership_invitations


def _process_workspace_project_invitations(user):
    """This function takes in User and adds him to all workspace and projects that the user has accepted invited of"""

    # Check if user has any accepted invites for workspace and add them to workspace
    workspace_member_invites = accepted_membership_invitations(user.email, for_update=True)

    WorkspaceMember.objects.bulk_create(
        [
            WorkspaceMember(
                workspace_id=workspace_member_invite.workspace_id,
                member=user,
                role=workspace_member_invite.role,
            )
            for workspace_member_invite in workspace_member_invites
        ],
        ignore_conflicts=True,
    )

    for workspace_member_invite in workspace_member_invites:
        cache_kwargs = {
            "path": f"/api/workspaces/{str(workspace_member_invite.workspace.slug)}/members/",
            "url_params": False,
            "user": False,
            "multiple": True,
        }
        transaction.on_commit(lambda kwargs=cache_kwargs: invalidate_cache_directly(**kwargs))
        event_kwargs = {
            "user_id": user.id,
            "event_name": USER_JOINED_WORKSPACE,
            "slug": workspace_member_invite.workspace.slug,
            "event_properties": {
                "user_id": user.id,
                "workspace_id": workspace_member_invite.workspace.id,
                "workspace_slug": workspace_member_invite.workspace.slug,
                "role": workspace_member_invite.role,
                "joined_at": str(timezone.now().isoformat()),
            },
        }
        transaction.on_commit(lambda kwargs=event_kwargs: track_event.delay(**kwargs))

    # Check if user has any project invites
    project_member_invites = ProjectMemberInvite.objects.filter(email=user.email, accepted=True)

    # Add user to workspace
    WorkspaceMember.objects.bulk_create(
        [
            WorkspaceMember(
                workspace_id=project_member_invite.workspace_id,
                role=(project_member_invite.role if project_member_invite.role in [5, 15] else 15),
                member=user,
                created_by_id=project_member_invite.created_by_id,
            )
            for project_member_invite in project_member_invites
        ],
        ignore_conflicts=True,
    )

    # Now add the users to project
    ProjectMember.objects.bulk_create(
        [
            ProjectMember(
                workspace_id=project_member_invite.workspace_id,
                role=(project_member_invite.role if project_member_invite.role in [5, 15] else 15),
                member=user,
                created_by_id=project_member_invite.created_by_id,
            )
            for project_member_invite in project_member_invites
        ],
        ignore_conflicts=True,
    )

    # Delete all the invites
    consumed_at = timezone.now()
    workspace_member_invites.update(consumed_at=consumed_at, deleted_at=consumed_at)
    project_member_invites.delete()


def process_workspace_project_invitations(user):
    """Consume accepted workspace/project invitations in one transaction."""
    with transaction.atomic():
        _process_workspace_project_invitations(user)
