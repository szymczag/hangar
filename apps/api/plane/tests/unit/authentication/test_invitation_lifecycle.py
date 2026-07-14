# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from plane.authentication.services.invitations import active_signup_invitations
from plane.authentication.utils.workspace_project_join import process_workspace_project_invitations
from plane.db.models import WorkspaceMember, WorkspaceMemberInvite
from plane.tests.factories import UserFactory, WorkspaceFactory


def create_invite(workspace, email, **overrides):
    values = {
        "workspace": workspace,
        "email": email,
        "token": "invitation-token",
        "expires_at": timezone.now() + timedelta(days=1),
    }
    values.update(overrides)
    return WorkspaceMemberInvite.objects.create(**values)


@pytest.mark.django_db
def test_only_pending_unexpired_invite_authorizes_signup():
    workspace = WorkspaceFactory()
    email = "invitee@hangar.test"
    active = create_invite(workspace, email)

    assert list(active_signup_invitations(email)) == [active]

    active.responded_at = timezone.now()
    active.accepted = False
    active.revoked_at = active.responded_at
    active.save()
    assert not active_signup_invitations(email).exists()


@pytest.mark.django_db(transaction=True)
def test_accepted_invite_is_consumed_transactionally(mocker):
    mocker.patch("plane.authentication.utils.workspace_project_join.invalidate_cache_directly")
    mocker.patch("plane.authentication.utils.workspace_project_join.track_event.delay")
    user = UserFactory(email="invitee@hangar.test")
    workspace = WorkspaceFactory()
    invite = create_invite(
        workspace,
        user.email,
        accepted=True,
        responded_at=timezone.now(),
        signup_authorized_at=timezone.now(),
    )

    process_workspace_project_invitations(user)

    assert WorkspaceMember.objects.filter(workspace=workspace, member=user).exists()
    assert not WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_expired_accepted_invite_grants_no_membership():
    user = UserFactory(email="expired@hangar.test")
    workspace = WorkspaceFactory()
    invite = create_invite(
        workspace,
        user.email,
        accepted=True,
        responded_at=timezone.now(),
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    process_workspace_project_invitations(user)

    assert not WorkspaceMember.objects.filter(workspace=workspace, member=user).exists()
    assert WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_direct_accept_rejects_expired_invitation():
    user = UserFactory(email="direct-expired@hangar.test", username="direct-expired")
    workspace = WorkspaceFactory()
    invite = create_invite(
        workspace,
        user.email,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        reverse("workspace-join", kwargs={"slug": workspace.slug, "pk": invite.pk}),
        {"token": invite.token, "accepted": True},
        format="json",
    )

    assert response.status_code == 400
    assert not WorkspaceMember.objects.filter(workspace=workspace, member=user).exists()


@pytest.mark.django_db(transaction=True)
def test_direct_accept_consumes_active_invitation(mocker):
    mocker.patch("plane.app.views.workspace.invite.track_event.delay")
    user = UserFactory(email="direct-active@hangar.test", username="direct-active")
    workspace = WorkspaceFactory()
    invite = create_invite(workspace, user.email)
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        reverse("workspace-join", kwargs={"slug": workspace.slug, "pk": invite.pk}),
        {"token": invite.token, "accepted": True},
        format="json",
    )

    assert response.status_code == 200
    assert WorkspaceMember.objects.filter(workspace=workspace, member=user).exists()
    assert not WorkspaceMemberInvite.objects.filter(pk=invite.pk).exists()
    archived = WorkspaceMemberInvite.all_objects.get(pk=invite.pk)
    assert archived.consumed_at is not None
