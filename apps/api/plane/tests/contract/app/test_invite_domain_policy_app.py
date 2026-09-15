# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The domain policy must reach the invitation endpoints, not only sign-in.

Enforcement lived solely in the authentication adapter, so an admin could
create an invitation the policy would later refuse: the row was written and the
invitation email was sent to an outsider before anyone discovered the account
could not be created. These tests pin the refusal to the moment of the mistake,
across every endpoint that writes an invitation — the app endpoints and the v1
API, which would otherwise be a way around the restriction.
"""

import pytest
from rest_framework import status

from uuid import uuid4

from rest_framework.test import APIClient

from plane.db.models import (
    Project,
    ProjectMember,
    ProjectMemberInvite,
    User,
    WorkspaceMember,
    WorkspaceMemberInvite,
)
from plane.license.models import InstanceConfiguration


def _store(key, value):
    InstanceConfiguration.objects.update_or_create(
        key=key, defaults={"value": value, "category": "SSO", "is_encrypted": False}
    )


@pytest.fixture
def confined_instance(db):
    """corp.com is pinned to OIDC, and invitations are confined to it."""
    _store("SSO_ENFORCED_DOMAINS", "corp.com=oidc")
    _store("RESTRICT_INVITES_TO_SSO_DOMAINS", "1")


@pytest.fixture
def pinned_but_unconfined_instance(db):
    """corp.com is pinned, but invitations are not confined to it."""
    _store("SSO_ENFORCED_DOMAINS", "corp.com=oidc")
    _store("RESTRICT_INVITES_TO_SSO_DOMAINS", "0")


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Policy Project", identifier="POL", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20, is_active=True)
    return project


def _workspace_user(workspace, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"person-{uid}@plane.so", username=f"person_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    return user


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _workspace_invite_url(slug):
    return f"/api/workspaces/{slug}/invitations/"


def _project_invite_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/invitations/"


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkspaceInviteDomainPolicy:
    def test_outside_domain_is_refused(self, session_client, workspace, confined_instance):
        response = session_client.post(
            _workspace_invite_url(workspace.slug),
            {"emails": [{"email": "outsider@gmail.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert not WorkspaceMemberInvite.objects.filter(email="outsider@gmail.com").exists()

    def test_pinned_domain_is_accepted(self, session_client, workspace, confined_instance):
        response = session_client.post(
            _workspace_invite_url(workspace.slug),
            {"emails": [{"email": "person@corp.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert WorkspaceMemberInvite.objects.filter(email="person@corp.com").exists()

    def test_plus_tag_on_a_pinned_domain_is_refused(self, session_client, workspace, confined_instance):
        response = session_client.post(
            _workspace_invite_url(workspace.slug),
            {"emails": [{"email": "person+team@corp.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert not WorkspaceMemberInvite.objects.filter(email="person+team@corp.com").exists()

    def test_plus_tag_is_refused_even_when_invites_are_not_confined(
        self, session_client, workspace, pinned_but_unconfined_instance
    ):
        """The address is unreachable through the pinned provider either way."""
        response = session_client.post(
            _workspace_invite_url(workspace.slug),
            {"emails": [{"email": "person+team@corp.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_outside_domain_is_accepted_when_invites_are_not_confined(
        self, session_client, workspace, pinned_but_unconfined_instance
    ):
        """The default, so an instance inviting contractors keeps working."""
        response = session_client.post(
            _workspace_invite_url(workspace.slug),
            {"emails": [{"email": "contractor@gmail.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_one_refused_address_writes_none_of_the_batch(self, session_client, workspace, confined_instance):
        response = session_client.post(
            _workspace_invite_url(workspace.slug),
            {
                "emails": [
                    {"email": "person@corp.com", "role": 15},
                    {"email": "outsider@gmail.com", "role": 15},
                ]
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not WorkspaceMemberInvite.objects.filter(email="person@corp.com").exists()


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectInviteDomainPolicy:
    def test_outside_domain_is_refused(self, session_client, workspace, project, confined_instance):
        response = session_client.post(
            _project_invite_url(workspace.slug, project.id),
            {"emails": [{"email": "outsider@gmail.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert not ProjectMemberInvite.objects.filter(email="outsider@gmail.com").exists()

    def test_pinned_domain_is_accepted(self, session_client, workspace, project, confined_instance):
        response = session_client.post(
            _project_invite_url(workspace.slug, project.id),
            {"emails": [{"email": "person@corp.com", "role": 15}]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )


@pytest.mark.contract
@pytest.mark.django_db
class TestApiInviteDomainPolicy:
    """The v1 API must not be a way around the restriction."""

    def test_outside_domain_is_refused(self, api_key_client, workspace, confined_instance):
        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/invitations/",
            {"email": "outsider@gmail.com", "role": 15},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert not WorkspaceMemberInvite.objects.filter(email="outsider@gmail.com").exists()

    def test_plus_tag_on_a_pinned_domain_is_refused(self, api_key_client, workspace, confined_instance):
        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/invitations/",
            {"email": "person+team@corp.com", "role": 15},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_pinned_domain_is_accepted(self, api_key_client, workspace, confined_instance):
        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/invitations/",
            {"email": "person@corp.com", "role": 15},
            format="json",
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )


@pytest.mark.contract
@pytest.mark.django_db
class TestInvitationPolicyEndpoint:
    """What the invite dialog reads to refuse an address before submitting."""

    def test_admin_reads_the_policy(self, session_client, workspace, confined_instance):
        response = session_client.get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
        assert response.json() == {
            "restrict_to_domains": True,
            "domains": {"corp.com": {"allows_sign_in": True, "allows_plus_tags": False}},
        }

    def test_a_domain_allowing_magic_codes_keeps_its_plus_tags(self, session_client, workspace, db):
        _store("SSO_ENFORCED_DOMAINS", "corp.com=oidc;magic-code")
        _store("RESTRICT_INVITES_TO_SSO_DOMAINS", "1")
        response = session_client.get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.json()["domains"]["corp.com"]["allows_plus_tags"] is True

    def test_restriction_reads_false_while_no_domain_is_pinned(self, session_client, workspace, db):
        # Confining invitations to an empty list would refuse every address, so
        # the flag is reported off until a domain exists to confine them to.
        _store("SSO_ENFORCED_DOMAINS", "")
        _store("RESTRICT_INVITES_TO_SSO_DOMAINS", "1")
        response = session_client.get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.json() == {"restrict_to_domains": False, "domains": {}}

    def test_a_member_reads_it_because_the_create_endpoint_admits_members_too(self, workspace, confined_instance):
        """WorkSpaceAdminPermission admits members despite its name, and this
        endpoint must not be narrower than the one that writes invitations."""
        client = _client_for(_workspace_user(workspace, role=15))

        response = client.get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.status_code == status.HTTP_200_OK, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_a_guest_cannot_read_the_policy(self, workspace, confined_instance):
        client = _client_for(_workspace_user(workspace, role=5))

        response = client.get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_someone_outside_the_workspace_cannot_read_the_policy(self, workspace, confined_instance):
        outsider = User.objects.create(email=f"outsider-{uuid4().hex[:8]}@plane.so", username=uuid4().hex[:8])

        response = _client_for(outsider).get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.status_code == status.HTTP_403_FORBIDDEN, (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )

    def test_an_anonymous_caller_cannot_read_the_policy(self, workspace, confined_instance):
        response = APIClient().get(_workspace_invite_url(workspace.slug) + "policy/")
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN), (
            f"Got {response.status_code}: {getattr(response, 'data', None)!r}"
        )
