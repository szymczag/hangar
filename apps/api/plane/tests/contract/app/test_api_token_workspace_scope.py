# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A token names the workspace it may act in, and minting one takes a role.

Before this, any signed-in account could mint a token, and the token reached
every workspace its owner belonged to. Someone who was a guest in one workspace
and an administrator of their own could therefore act through the token in the
first — the role they held where it mattered never entered into it.

Naming the workspace is what makes a role requirement mean anything, so both
halves are tested together.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from plane.app.permissions.base import ROLE
from plane.db.models import APIToken
from plane.license.models import InstanceConfiguration
from plane.tests.factories import UserFactory, WorkspaceFactory, WorkspaceMemberFactory

URL_NAME = "api-tokens"


def _set_minimum_role(value):
    InstanceConfiguration.objects.update_or_create(
        key="API_TOKEN_MINIMUM_ROLE",
        defaults={"value": str(value), "category": "WORKSPACE_MANAGEMENT", "is_encrypted": False},
    )


@pytest.fixture
def actor(db):
    return UserFactory()


@pytest.fixture
def client_for(actor):
    client = APIClient()
    client.force_authenticate(user=actor)
    return client


def _mint(client, **payload):
    return client.post(reverse(URL_NAME), payload, format="json")


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_records_the_workspace_it_was_minted_for(client_for, actor):
    workspace = WorkspaceFactory(owner=actor)
    WorkspaceMemberFactory(workspace=workspace, member=actor, role=ROLE.MEMBER.value)
    _set_minimum_role(ROLE.GUEST.value)

    response = _mint(client_for, label="ci", workspace_slug=workspace.slug)

    assert response.status_code == status.HTTP_201_CREATED
    assert APIToken.objects.get(pk=response.data["id"]).workspace_id == workspace.id


@pytest.mark.contract
@pytest.mark.django_db
def test_a_role_below_the_threshold_cannot_mint_one(client_for, actor):
    """The case the setting exists for."""
    workspace = WorkspaceFactory(owner=actor)
    WorkspaceMemberFactory(workspace=workspace, member=actor, role=ROLE.GUEST.value)
    _set_minimum_role(ROLE.MEMBER.value)

    response = _mint(client_for, label="ci", workspace_slug=workspace.slug)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert not APIToken.objects.filter(user=actor).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_holding_the_role_elsewhere_does_not_help(client_for, actor):
    """The escalation the old behaviour allowed, stated as a test.

    Being an administrator of one's own workspace used to be enough to mint a
    token that reached a workspace where one was only a guest.
    """
    own = WorkspaceFactory(owner=actor, slug="own-workspace")
    WorkspaceMemberFactory(workspace=own, member=actor, role=ROLE.ADMIN.value)
    other = WorkspaceFactory(slug="other-workspace")
    WorkspaceMemberFactory(workspace=other, member=actor, role=ROLE.GUEST.value)
    _set_minimum_role(ROLE.MEMBER.value)

    assert _mint(client_for, workspace_slug=other.slug).status_code == status.HTTP_403_FORBIDDEN
    assert _mint(client_for, workspace_slug=own.slug).status_code == status.HTTP_201_CREATED


@pytest.mark.contract
@pytest.mark.django_db
def test_a_workspace_the_caller_does_not_belong_to_is_refused(client_for, actor):
    stranger = WorkspaceFactory(slug="not-mine")
    _set_minimum_role(ROLE.GUEST.value)

    response = _mint(client_for, workspace_slug=stranger.slug)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unknown_workspace_is_answered_the_same_way(client_for):
    """Membership and existence must not be distinguishable from the outside."""
    _set_minimum_role(ROLE.GUEST.value)

    unknown = _mint(client_for, workspace_slug="no-such-workspace")

    assert unknown.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_a_deactivated_membership_does_not_count(client_for, actor):
    workspace = WorkspaceFactory(owner=actor)
    WorkspaceMemberFactory(workspace=workspace, member=actor, role=ROLE.ADMIN.value, is_active=False)
    _set_minimum_role(ROLE.GUEST.value)

    response = _mint(client_for, workspace_slug=workspace.slug)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_without_a_workspace_is_refused(client_for):
    """Every new token names one; the field is no longer decorative."""
    response = _mint(client_for, label="ci")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
def test_the_threshold_comes_from_stored_configuration(client_for, actor):
    """Read through get_configuration_value, not from the environment."""
    workspace = WorkspaceFactory(owner=actor)
    WorkspaceMemberFactory(workspace=workspace, member=actor, role=ROLE.MEMBER.value)

    _set_minimum_role(ROLE.ADMIN.value)
    assert _mint(client_for, workspace_slug=workspace.slug).status_code == status.HTTP_403_FORBIDDEN

    _set_minimum_role(ROLE.MEMBER.value)
    assert _mint(client_for, workspace_slug=workspace.slug).status_code == status.HTTP_201_CREATED


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unreadable_threshold_falls_back_to_the_previous_behaviour(client_for, actor):
    """A broken setting must neither open the gate nor weld it shut."""
    workspace = WorkspaceFactory(owner=actor)
    WorkspaceMemberFactory(workspace=workspace, member=actor, role=ROLE.GUEST.value)
    _set_minimum_role("not-a-number")

    assert _mint(client_for, workspace_slug=workspace.slug).status_code == status.HTTP_201_CREATED


@pytest.mark.contract
def test_only_the_callers_own_records_are_reachable_without_a_workspace():
    """Guards the assumption that lets a scoped token skip slug-less routes.

    BaseAPIView.initial() confines a scoped token by comparing the token's
    workspace to the slug in the URL, so a route with no slug is not confined at
    all. That is right only while every such route addresses the caller's own
    record. If a workspace-bound route ever appears without a slug, the
    confinement would not cover it and this fails.
    """
    from plane.tests.support.route_inventory import collect_routes

    known_user_scoped = {
        "api/v1/users/me/",
        "api/v1/assets/user-assets/",
        "api/v1/assets/user-assets/<uuid:asset_id>/",
        "api/v1/assets/user-assets/server/",
        "api/v1/assets/user-assets/<uuid:asset_id>/server/",
    }

    unconfined = {
        record.pattern
        for record in collect_routes()
        if record.pattern.startswith("api/v1/") and "slug" not in record.kwargs_required
    }

    assert unconfined <= known_user_scoped, (
        "External API routes without a workspace slug are not covered by token scope "
        f"confinement: {sorted(unconfined - known_user_scoped)}"
    )
