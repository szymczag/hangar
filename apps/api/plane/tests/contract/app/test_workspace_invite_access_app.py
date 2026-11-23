# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Who may write, read and withdraw a workspace's invitations.

The endpoints carried ``WorkSpaceAdminPermission``, which admits members as
well as admins despite its name. Any member could invite, change the role of
any pending invitation and withdraw one an admin had sent. Inviting is now an
admin's act unless the instance sets ``ALLOW_MEMBERS_TO_INVITE``; then a member
invites at most at their own role and manages only what they sent. Guests
never.
"""

from importlib import import_module
from uuid import uuid4

import pytest
from django.apps import apps as django_apps
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from plane.authentication.utils.sso_domain_policy import invitation_policy_snapshot
from plane.db.models import User, WorkspaceMember, WorkspaceMemberInvite
from plane.license.models import InstanceConfiguration
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.utils.instance_config_variables import instance_config_variables
from plane.utils.invite_policy import members_can_invite

ADMIN, MEMBER, GUEST = 20, 15, 5

setup_instance = _google_auth.setup_instance


def _allow_members(value):
    InstanceConfiguration.objects.update_or_create(
        key="ALLOW_MEMBERS_TO_INVITE",
        defaults={"value": value, "category": "WORKSPACE_MANAGEMENT", "is_encrypted": False},
    )


@pytest.fixture
def members_may_invite(db):
    _allow_members("1")


@pytest.fixture
def members_may_not_invite(db):
    _allow_members("0")


def _user_with_role(workspace, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"person-{uid}@plane.so", username=f"person_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    return user


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _invite(workspace, created_by, role=MEMBER):
    invite = WorkspaceMemberInvite(
        workspace=workspace,
        email=f"invitee-{uuid4().hex[:8]}@plane.so",
        token=uuid4().hex,
        role=role,
    )
    # BaseModel.save() takes the sender from the request in flight and ignores a
    # created_by passed to the constructor; outside a request it would be None.
    invite.save(created_by_id=created_by.id if created_by else None)
    return invite


def _list_url(slug):
    return f"/api/workspaces/{slug}/invitations/"


def _detail_url(slug, pk):
    return f"/api/workspaces/{slug}/invitations/{pk}/"


def _create(client, slug, role=MEMBER):
    email = f"new-{uuid4().hex[:8]}@plane.so"
    response = client.post(_list_url(slug), {"emails": [{"email": email, "role": role}]}, format="json")
    return response, email


def _detail(response):
    return f"Got {response.status_code}: {getattr(response, 'data', None)!r}"


@pytest.mark.contract
@pytest.mark.django_db
class TestAdminsKeepFullRights:
    @pytest.mark.parametrize("setting", ["0", "1"])
    def test_admin_lists_creates_updates_and_withdraws_any_invitation(self, session_client, workspace, setting):
        _allow_members(setting)
        someone_else = _user_with_role(workspace, MEMBER)
        invite = _invite(workspace, created_by=someone_else)

        response = session_client.get(_list_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK, _detail(response)

        response, email = _create(session_client, workspace.slug, role=ADMIN)
        assert response.status_code == status.HTTP_200_OK, _detail(response)
        assert WorkspaceMemberInvite.objects.filter(email=email, role=ADMIN).exists()

        response = session_client.patch(_detail_url(workspace.slug, invite.id), {"role": ADMIN}, format="json")
        assert response.status_code == status.HTTP_200_OK, _detail(response)

        response = session_client.delete(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT, _detail(response)
        assert not WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()


@pytest.mark.contract
@pytest.mark.django_db
class TestMembersCannotInviteByDefault:
    def test_the_setting_defaults_to_off(self, db):
        InstanceConfiguration.objects.filter(key="ALLOW_MEMBERS_TO_INVITE").delete()
        assert members_can_invite() is False

    def test_member_cannot_list(self, workspace, members_may_not_invite):
        client = _client_for(_user_with_role(workspace, MEMBER))
        response = client.get(_list_url(workspace.slug))
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)

    def test_member_cannot_create(self, workspace, members_may_not_invite):
        client = _client_for(_user_with_role(workspace, MEMBER))
        response, email = _create(client, workspace.slug, role=GUEST)
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)
        assert not WorkspaceMemberInvite.objects.filter(email=email).exists()

    def test_member_cannot_change_the_role_even_of_their_own_invitation(self, workspace, members_may_not_invite):
        # Sent while the setting was on; turning it off takes the right back.
        member = _user_with_role(workspace, MEMBER)
        invite = _invite(workspace, created_by=member)

        response = _client_for(member).patch(_detail_url(workspace.slug, invite.id), {"role": GUEST}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)
        invite.refresh_from_db()
        assert invite.role == MEMBER

    def test_member_cannot_withdraw_an_admins_invitation(self, workspace, create_user, members_may_not_invite):
        invite = _invite(workspace, created_by=create_user, role=ADMIN)

        response = _client_for(_user_with_role(workspace, MEMBER)).delete(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)
        assert WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()

    def test_member_cannot_read_one_invitation(self, workspace, create_user, members_may_not_invite):
        invite = _invite(workspace, created_by=create_user)

        response = _client_for(_user_with_role(workspace, MEMBER)).get(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)

    @pytest.mark.parametrize("value", ["", "true", "yes", " 0 ", "2"])
    def test_anything_but_one_reads_as_off(self, workspace, value):
        _allow_members(value)
        client = _client_for(_user_with_role(workspace, MEMBER))
        response, _ = _create(client, workspace.slug, role=GUEST)
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)


@pytest.mark.contract
@pytest.mark.django_db
class TestMembersInviteWhereTheInstanceAllows:
    """Someone else's invitation is invisible to a member: 404 on read, change and withdraw."""

    def test_member_lists_only_their_own_invitations(self, workspace, create_user, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        own = _invite(workspace, created_by=member)
        _invite(workspace, created_by=create_user)
        _invite(workspace, created_by=_user_with_role(workspace, MEMBER))

        response = _client_for(member).get(_list_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK, _detail(response)
        assert [row["id"] for row in response.json()] == [str(own.id)]

    def test_admin_still_lists_every_invitation(self, session_client, workspace, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        invites = {_invite(workspace, created_by=member).id, _invite(workspace, created_by=None).id}

        response = session_client.get(_list_url(workspace.slug))
        assert response.status_code == status.HTTP_200_OK, _detail(response)
        assert {row["id"] for row in response.json()} >= {str(pk) for pk in invites}

    def test_member_reads_their_own_invitation(self, workspace, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        invite = _invite(workspace, created_by=member)

        response = _client_for(member).get(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_200_OK, _detail(response)

    def test_member_cannot_read_someone_elses_invitation(self, workspace, create_user, members_may_invite):
        invite = _invite(workspace, created_by=create_user)

        response = _client_for(_user_with_role(workspace, MEMBER)).get(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND, _detail(response)

    def test_member_invites_up_to_their_own_role(self, workspace, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        response, email = _create(_client_for(member), workspace.slug, role=MEMBER)
        assert response.status_code == status.HTTP_200_OK, _detail(response)
        assert WorkspaceMemberInvite.objects.get(email=email).created_by_id == member.id

    def test_member_cannot_invite_an_admin(self, workspace, members_may_invite):
        response, email = _create(_client_for(_user_with_role(workspace, MEMBER)), workspace.slug, role=ADMIN)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, _detail(response)
        assert not WorkspaceMemberInvite.objects.filter(email=email).exists()

    def test_member_changes_their_own_invitation(self, workspace, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        invite = _invite(workspace, created_by=member)

        response = _client_for(member).patch(_detail_url(workspace.slug, invite.id), {"role": GUEST}, format="json")
        assert response.status_code == status.HTTP_200_OK, _detail(response)
        invite.refresh_from_db()
        assert invite.role == GUEST

    def test_member_withdraws_their_own_invitation(self, workspace, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        invite = _invite(workspace, created_by=member)

        response = _client_for(member).delete(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT, _detail(response)
        assert not WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()

    def test_member_cannot_change_someone_elses_invitation(self, workspace, create_user, members_may_invite):
        invite = _invite(workspace, created_by=create_user)

        client = _client_for(_user_with_role(workspace, MEMBER))
        response = client.patch(_detail_url(workspace.slug, invite.id), {"role": GUEST}, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND, _detail(response)
        invite.refresh_from_db()
        assert invite.role == MEMBER

    def test_member_cannot_withdraw_someone_elses_invitation(self, workspace, create_user, members_may_invite):
        invite = _invite(workspace, created_by=create_user, role=ADMIN)

        response = _client_for(_user_with_role(workspace, MEMBER)).delete(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND, _detail(response)
        assert WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()

    def test_member_cannot_withdraw_another_members_invitation(self, workspace, members_may_invite):
        sender = _user_with_role(workspace, MEMBER)
        invite = _invite(workspace, created_by=sender)

        response = _client_for(_user_with_role(workspace, MEMBER)).delete(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND, _detail(response)
        assert WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()

    def test_an_invitation_with_no_sender_is_left_to_admins(self, workspace, members_may_invite):
        invite = _invite(workspace, created_by=None)

        response = _client_for(_user_with_role(workspace, MEMBER)).delete(_detail_url(workspace.slug, invite.id))
        assert response.status_code == status.HTTP_404_NOT_FOUND, _detail(response)


@pytest.mark.contract
@pytest.mark.django_db
class TestGuestsAndOutsidersNever:
    @pytest.mark.parametrize("setting", ["0", "1"])
    def test_guest_is_refused_everything(self, workspace, create_user, setting):
        _allow_members(setting)
        guest = _user_with_role(workspace, GUEST)
        client = _client_for(guest)
        others = _invite(workspace, created_by=create_user)
        # A guest who was a member when they sent it does not keep the right.
        own = _invite(workspace, created_by=guest)

        assert client.get(_list_url(workspace.slug)).status_code == status.HTTP_403_FORBIDDEN
        assert client.get(_list_url(workspace.slug) + "policy/").status_code == status.HTTP_403_FORBIDDEN
        response, _ = _create(client, workspace.slug, role=GUEST)
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)
        for invite in (others, own):
            url = _detail_url(workspace.slug, invite.id)
            assert client.patch(url, {"role": GUEST}, format="json").status_code == status.HTTP_403_FORBIDDEN
            assert client.delete(url).status_code == status.HTTP_403_FORBIDDEN
        assert WorkspaceMemberInvite.objects.filter(pk__in=[others.pk, own.pk]).count() == 2

    def test_inactive_member_is_refused(self, workspace, members_may_invite):
        member = _user_with_role(workspace, MEMBER)
        WorkspaceMember.objects.filter(member=member).update(is_active=False)

        response, _ = _create(_client_for(member), workspace.slug, role=GUEST)
        assert response.status_code == status.HTTP_403_FORBIDDEN, _detail(response)

    def test_admin_of_another_workspace_is_refused(self, workspace, create_user, members_may_invite):
        outsider = User.objects.create(email=f"outsider-{uuid4().hex[:8]}@plane.so", username=uuid4().hex[:8])
        invite = _invite(workspace, created_by=create_user)

        client = _client_for(outsider)
        assert client.get(_list_url(workspace.slug)).status_code == status.HTTP_403_FORBIDDEN
        assert client.delete(_detail_url(workspace.slug, invite.id)).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
class TestTheSettingItself:
    def test_declared_off_with_the_other_instance_settings(self):
        (declared,) = [item for item in instance_config_variables if item["key"] == "ALLOW_MEMBERS_TO_INVITE"]
        assert declared["category"] == "WORKSPACE_MANAGEMENT"
        assert declared["is_encrypted"] is False

    def test_the_migration_seeds_it_off(self, monkeypatch):
        monkeypatch.delenv("ALLOW_MEMBERS_TO_INVITE", raising=False)
        InstanceConfiguration.objects.filter(key="ALLOW_MEMBERS_TO_INVITE").delete()
        migration = import_module("plane.license.migrations.0025_allow_members_to_invite")

        migration.seed_allow_members_to_invite(django_apps, schema_editor=None)

        stored = InstanceConfiguration.objects.get(key="ALLOW_MEMBERS_TO_INVITE")
        assert (stored.value, stored.category, stored.is_encrypted) == ("0", "WORKSPACE_MANAGEMENT", False)

    def test_the_migration_keeps_a_value_already_stored(self, members_may_invite):
        migration = import_module("plane.license.migrations.0025_allow_members_to_invite")

        migration.seed_allow_members_to_invite(django_apps, schema_editor=None)

        assert InstanceConfiguration.objects.get(key="ALLOW_MEMBERS_TO_INVITE").value == "1"

    def test_the_snapshot_reports_it(self, members_may_invite):
        assert invitation_policy_snapshot()["members_can_invite"] is True
        _allow_members("0")
        assert invitation_policy_snapshot()["members_can_invite"] is False

    @pytest.mark.parametrize("setting, expected", [("1", True), ("0", False)])
    def test_the_signed_in_instance_payload_reports_it(self, workspace, setup_instance, setting, expected):
        """What the application reads before it offers an invite button."""
        _allow_members(setting)
        cache.clear()
        client = _client_for(_user_with_role(workspace, MEMBER))

        response = client.get("/api/users/me/instance-config/")
        cache.clear()
        assert response.status_code == status.HTTP_200_OK, _detail(response)
        assert response.data["config"]["members_can_invite"] is expected
