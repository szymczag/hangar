# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An invitation to a workspace you already belong to has nothing left to offer.

Invitations are consumed when accepted through the emailed link. Somebody
invited by address who then signs in through the identity provider instead never
accepts one — auto-join adds the membership directly — so the invitation stays
outstanding and they appear under Members and Pending Invites at once.

It is not only untidy. An unaccepted invitation stays usable until it expires,
so once the person is removed from the workspace it is a way back in that nobody
granted.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from plane.authentication.utils.workspace_project_join import spend_invitations_already_honoured
from plane.db.models import Profile, User, Workspace, WorkspaceMember, WorkspaceMemberInvite


def _person(email="person@corp.com"):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    return user


def _workspace(owner, slug="acme"):
    return Workspace.objects.create(name="Acme", owner=owner, slug=slug)


def _invite(workspace, email, actor):
    return WorkspaceMemberInvite.objects.create(
        workspace=workspace,
        email=email,
        role=15,
        created_by=actor,
        expires_at=timezone.now() + timedelta(days=7),
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_stops_having_an_invitation_pending(db):
    owner = _person("owner@corp.com")
    workspace = _workspace(owner)
    user = _person()
    invite = _invite(workspace, user.email, owner)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)

    assert spend_invitations_already_honoured(user=user) == 1

    invite.refresh_from_db()
    assert invite.consumed_at is not None


@pytest.mark.contract
@pytest.mark.django_db
def test_the_address_is_matched_regardless_of_case(db):
    """Providers are inconsistent about this and an invitation is typed by hand."""
    owner = _person("owner@corp.com")
    workspace = _workspace(owner)
    user = _person("Person@Corp.com")
    invite = _invite(workspace, "person@corp.com", owner)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)

    spend_invitations_already_honoured(user=user)

    invite.refresh_from_db()
    assert invite.consumed_at is not None


@pytest.mark.contract
@pytest.mark.django_db
def test_an_invitation_to_somewhere_else_is_left_alone(db):
    """Belonging to one workspace says nothing about an invitation to another."""
    owner = _person("owner@corp.com")
    joined = _workspace(owner)
    elsewhere = _workspace(owner, slug="other")
    user = _person()
    invite = _invite(elsewhere, user.email, owner)
    WorkspaceMember.objects.create(workspace=joined, member=user, role=15, is_active=True)

    assert spend_invitations_already_honoured(user=user) == 0

    invite.refresh_from_db()
    assert invite.consumed_at is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_deactivated_membership_does_not_spend_it(db):
    """Someone removed from the workspace still needs a way to be let back in."""
    owner = _person("owner@corp.com")
    workspace = _workspace(owner)
    user = _person()
    invite = _invite(workspace, user.email, owner)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=False)

    assert spend_invitations_already_honoured(user=user) == 0

    invite.refresh_from_db()
    assert invite.consumed_at is None


@pytest.mark.contract
@pytest.mark.django_db
def test_belonging_nowhere_touches_nothing(db):
    owner = _person("owner@corp.com")
    workspace = _workspace(owner)
    user = _person()
    _invite(workspace, user.email, owner)

    assert spend_invitations_already_honoured(user=user) == 0
