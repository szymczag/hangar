# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Invitation updates (``PATCH /api/workspaces/<slug>/invitations/<pk>/``) may only
change ``role``, and members may only assign invitation roles up to their own
role, the same rule ``create()`` applies. A member reaches this endpoint at all
only where the instance lets members invite, and then only for an invitation
they sent (see test_workspace_invite_access_app.py).
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import WorkspaceMember, WorkspaceMemberInvite
from plane.license.models import InstanceConfiguration
from plane.tests.factories import UserFactory


def _url(slug, pk):
    return f"/api/workspaces/{slug}/invitations/{pk}/"


@pytest.fixture
def member_user(workspace):
    user = UserFactory(username="invite-member")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)
    InstanceConfiguration.objects.update_or_create(
        key="ALLOW_MEMBERS_TO_INVITE",
        defaults={"value": "1", "category": "WORKSPACE_MANAGEMENT", "is_encrypted": False},
    )
    return user


@pytest.fixture
def member_client(member_user):
    client = APIClient()
    client.force_authenticate(user=member_user)
    return client


@pytest.fixture
def invite(workspace):
    return WorkspaceMemberInvite.objects.create(workspace=workspace, email="invitee@plane.so", token="t", role=15)


@pytest.fixture
def member_invite(workspace, member_user):
    invite = WorkspaceMemberInvite(workspace=workspace, email="sent-by-member@plane.so", token="m", role=15)
    # BaseModel.save() ignores a created_by given to the constructor.
    invite.save(created_by_id=member_user.id)
    return invite


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkspaceInvitationUpdate:
    def test_member_invite_role_capped_at_own_role(self, member_client, workspace, member_invite):
        response = member_client.patch(_url(workspace.slug, member_invite.id), {"role": 20}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        member_invite.refresh_from_db()
        assert member_invite.role == 15

    def test_member_can_set_role_up_to_own(self, member_client, workspace, member_invite):
        response = member_client.patch(_url(workspace.slug, member_invite.id), {"role": 5}, format="json")

        assert response.status_code == status.HTTP_200_OK
        member_invite.refresh_from_db()
        assert member_invite.role == 5

    def test_admin_can_raise_invite_to_admin(self, session_client, workspace, invite):
        response = session_client.patch(_url(workspace.slug, invite.id), {"role": 20}, format="json")

        assert response.status_code == status.HTTP_200_OK
        invite.refresh_from_db()
        assert invite.role == 20

    @pytest.mark.parametrize("body", [{"accepted": True}, {"role": 5, "accepted": True}, ["role"]])
    def test_fields_other_than_role_are_rejected(self, session_client, workspace, invite, body):
        response = session_client.patch(_url(workspace.slug, invite.id), body, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        invite.refresh_from_db()
        assert invite.role == 15
        assert invite.accepted is False
