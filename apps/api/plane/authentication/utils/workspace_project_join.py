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
    WorkspaceMemberInvite,
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


def spend_invitations_already_honoured(user):
    """Retire invitations to workspaces this account is already a member of.

    Fork (see FORK.md): an invitation is consumed when it is accepted through
    the link. Somebody invited by email who then signs in through the identity
    provider instead — admitted by auto-join, or already a member — never
    accepts it, so it stays outstanding. Their name appears under Members and
    under Pending Invites at the same time, which is the reported symptom.

    It is not only untidy. An unaccepted invitation stays usable until it
    expires, so if the person is later removed from the workspace, that
    invitation is a way back in that nobody granted. Retiring it when the
    membership it was offering already exists closes that.

    Recorded as consumed in the same way an accepted one is, rather than
    deleted, so what happened to it remains legible.
    """
    memberships = WorkspaceMember.objects.filter(member=user, is_active=True).values_list("workspace_id", flat=True)
    if not memberships:
        return 0

    now = timezone.now()
    return WorkspaceMemberInvite.objects.filter(
        email__iexact=user.email,
        workspace_id__in=list(memberships),
        consumed_at__isnull=True,
        deleted_at__isnull=True,
    ).update(consumed_at=now, deleted_at=now)
