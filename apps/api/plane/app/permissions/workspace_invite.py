# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who may write, read and withdraw a workspace's invitations.

``WorkSpaceAdminPermission`` admits members as well as admins, despite its
name, and the invitation endpoints used it. A plain member could therefore
invite, change the role of any pending invitation, and withdraw one an admin
had sent. Inviting is an admin's act here unless the operator turns on
``ALLOW_MEMBERS_TO_INVITE``; then a member may invite (at most at their own
role, which the view checks) and see and manage the invitations they sent, and
nobody else's. Guests never.
"""

# Third party imports
from rest_framework.permissions import BasePermission

# Module imports
from plane.db.models import WorkspaceMember
from plane.utils.invite_policy import members_can_invite

ADMIN = 20
MEMBER = 15


def _workspace_role(request, view):
    if request.user.is_anonymous:
        return None
    return (
        WorkspaceMember.objects.filter(
            member=request.user,
            workspace__slug=view.workspace_slug,
            is_active=True,
        )
        .values_list("role", flat=True)
        .first()
    )


class WorkspaceInvitePermission(BasePermission):
    message = "Only workspace admins can manage invitations on this instance."

    def has_permission(self, request, view):
        role = _workspace_role(request, view)
        if role == ADMIN:
            return True
        return role == MEMBER and members_can_invite()

    def has_object_permission(self, request, view, obj):
        role = _workspace_role(request, view)
        if role == ADMIN:
            return True
        if role != MEMBER or not members_can_invite():
            return False
        # The view's queryset already hides other people's invitations from a
        # member (404); this is the same rule again, for every method.
        return obj.created_by_id is not None and obj.created_by_id == request.user.id
