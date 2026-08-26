# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Authorization on the surfaces the route probes cannot reach.

The matrix and horizontal probes drive session-authenticated requests against
routes that take a workspace slug. That leaves whole surfaces unexamined: the
token-authenticated external API, published boards served to anonymous callers,
assets addressed by bare id, and analytics endpoints whose scoping lives in a
shared filter helper rather than in the view.

Each test here states one property and proves it. Where the property does not
hold today the test carries a strict xfail naming the location, so the suite
stays honest without going red, and the marker must be removed by whoever fixes
it. Two suspicions were disproved while writing this and are kept as ordinary
tests, because "we checked, it is fine" is worth keeping too.
"""

import uuid

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import APIToken, DeployBoard, FileAsset, Webhook, WorkspaceMember
from plane.tests.support.personas import build_scenario
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION


@pytest.fixture
def scenario(db):
    return build_scenario()


def _token_client(user, workspace=None):
    token = APIToken.objects.create(user=user, label="probe", token=f"tok-{uuid.uuid4().hex}", workspace=workspace)
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    return client, token


def _session_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --------------------------------------------------------------------------
# External API token scoping
# --------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_api_token_is_limited_to_the_workspace_it_was_issued_for(scenario):
    """A token bound to workspace X should not act on workspace Y."""
    client, _ = _token_client(scenario.personas["member_a"], workspace=scenario.other_workspace)

    response = client.get(
        f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/issues/"
    )

    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_cannot_reach_a_workspace_its_owner_left(scenario):
    """The scoping that does hold: membership still governs the token."""
    client, _ = _token_client(scenario.personas["outsider"])

    response = client.get(
        f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/issues/"
    )

    assert response.status_code == 403
    assert scenario.project_a.canary not in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_renaming_an_api_token_does_not_return_its_secret(scenario):
    """Creation is the one moment the secret may be shown; a rename is not."""
    client = _session_client(scenario.personas["member_a"])
    created = client.post(
        "/api/users/api-tokens/",
        {"label": "original", "workspace_slug": scenario.workspace.slug},
        format="json",
    )
    token_id = created.json()["id"]

    renamed = client.patch(f"/api/users/api-tokens/{token_id}/", {"label": "renamed"}, format="json")

    assert '"token"' not in renamed.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_listing_api_tokens_never_returns_secrets(scenario):
    """The read path is correct and must stay that way."""
    client = _session_client(scenario.personas["member_a"])
    client.post(
        "/api/users/api-tokens/",
        {"label": "original", "workspace_slug": scenario.workspace.slug},
        format="json",
    )

    listed = client.get("/api/users/api-tokens/")

    assert listed.status_code == 200
    assert '"token"' not in listed.content.decode()


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_project_stats_require_membership_of_the_project(scenario):
    """A workspace member who is in no project should not get its counts.

    No issue content leaks, but sizes and membership counts of a project the
    caller cannot open are still information about it.
    """
    client = _session_client(scenario.personas["ws_member_no_project"])

    response = client.get(
        f"/api/workspaces/{scenario.workspace.slug}/project-stats/",
        {"project_ids": str(scenario.project_a.project.id)},
    )

    assert response.status_code == 403 or response.json() == []


@pytest.mark.contract
@pytest.mark.django_db
def test_project_stats_are_refused_to_a_non_member_of_the_workspace(scenario):
    """The outer boundary does hold."""
    client = _session_client(scenario.personas["outsider"])

    response = client.get(
        f"/api/workspaces/{scenario.workspace.slug}/project-stats/",
        {"project_ids": str(scenario.project_a.project.id)},
    )

    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_advance_analytics_ignore_project_ids_from_another_workspace(scenario):
    """Cross-tenant: the ids come from a workspace the caller has no part in."""
    client = _session_client(scenario.personas["other_owner"])
    base = f"/api/workspaces/{scenario.other_workspace.slug}/advance-analytics/"
    victim_members = WorkspaceMember.objects.filter(workspace=scenario.workspace, is_active=True).count()

    with_foreign = client.get(base, {"type": "overview", "project_ids": str(scenario.project_a.project.id)})

    # Ids from another workspace match nothing here, so the answer is zero —
    # and above all it is not the victim workspace's roster size.
    counted = with_foreign.json()["total_users"]["count"]
    assert counted == 0
    assert counted != victim_members


# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_workspace_logo_is_not_served_to_anonymous_callers(scenario):
    """Not content, but it tells a stranger which organisations use this instance."""
    logo = FileAsset.objects.create(
        workspace=scenario.workspace,
        entity_type="WORKSPACE_LOGO",
        asset="logo.png",
        attributes={"type": "image/png"},
        size=10,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )

    response = APIClient().get(f"/api/assets/v2/static/{logo.id}/")

    assert response.status_code >= 400


# --------------------------------------------------------------------------
# Published boards
# --------------------------------------------------------------------------


@pytest.fixture
def published_board(scenario):
    return DeployBoard.objects.create(
        workspace=scenario.workspace,
        project=scenario.project_a.project,
        entity_name="project",
        entity_identifier=scenario.project_a.project.id,
        is_disabled=False,
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_archiving_a_project_stops_its_published_board(scenario, published_board):
    """Suspected gap, disproved.

    plane/space/views/ never mentions archived_at, so a published board looked
    like it would keep serving an archived project. It does not — the issue
    queryset stops returning content.
    """
    anonymous = APIClient()
    url = f"/api/public/anchor/{published_board.anchor}/issues/"
    assert scenario.project_a.canary in anonymous.get(url).content.decode()

    scenario.project_a.project.archived_at = timezone.now()
    scenario.project_a.project.save()

    response = anonymous.get(url)
    assert scenario.project_a.canary not in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_published_board_exposes_its_member_roster(scenario, published_board):
    """Intended, and pinned so it cannot change unnoticed.

    plane/space/views/project.py:80-101 returns display names and avatars of a
    published project's members to unauthenticated callers. Confirmed as
    intended for public boards; this test exists so widening or narrowing it is
    a deliberate act.
    """
    response = APIClient().get(f"/api/public/anchor/{published_board.anchor}/members/")

    assert response.status_code == 200
    assert len(response.json()) > 0
    body = response.content.decode()
    assert scenario.project_a.canary not in body
    assert scenario.owner.email not in body, "email addresses must not be part of the public roster"


# --------------------------------------------------------------------------
# Member listings and webhooks
# --------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_member_listing_excludes_deactivated_memberships(scenario):
    removed = scenario.personas["ws_member_no_project"]
    WorkspaceMember.objects.filter(workspace=scenario.workspace, member=removed).update(is_active=False)
    client, _ = _token_client(scenario.owner)

    response = client.get(f"/api/v1/workspaces/{scenario.workspace.slug}/members/")

    assert removed.email not in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_webhook_secret_is_never_listed(scenario):
    """Suspected gap, disproved.

    The `fields=(...)` allowlists passed at the call sites are dead code, so the
    listing was expected to carry everything. The serializer removes secret_key
    unless explicitly asked, and only create and regenerate ask.
    """
    webhook = Webhook.objects.create(workspace=scenario.workspace, url="https://example.com/hook")
    client = _session_client(scenario.owner)

    response = client.get(f"/api/workspaces/{scenario.workspace.slug}/webhooks/")

    assert response.status_code == 200
    assert webhook.secret_key not in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_webhooks_are_not_readable_by_ordinary_members(scenario):
    client = _session_client(scenario.personas["ws_member_no_project"])

    response = client.get(f"/api/workspaces/{scenario.workspace.slug}/webhooks/")

    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_user_avatars_remain_public(scenario):
    """Rendered on sign-in screens and public boards; must not need a session."""
    avatar = FileAsset.objects.create(
        user=scenario.owner,
        entity_type="USER_AVATAR",
        asset="avatar.png",
        attributes={"type": "image/png"},
        size=10,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )

    response = APIClient().get(f"/api/assets/v2/static/{avatar.id}/")

    assert response.status_code == 302


@pytest.mark.contract
@pytest.mark.django_db
def test_a_workspace_member_can_still_read_the_logo(scenario):
    """The fix must not cost the people it is meant to serve."""
    logo = FileAsset.objects.create(
        workspace=scenario.workspace,
        entity_type="WORKSPACE_LOGO",
        asset="logo.png",
        attributes={"type": "image/png"},
        size=10,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )

    response = _session_client(scenario.personas["member_a"]).get(f"/api/assets/v2/static/{logo.id}/")

    assert response.status_code == 302


@pytest.mark.contract
@pytest.mark.django_db
def test_project_cover_follows_publication(scenario):
    """A cover is public exactly while its project is.

    The public board lists cover_image, so gating covers on membership alone
    would break published boards.
    """
    cover = FileAsset.objects.create(
        workspace=scenario.workspace,
        project=scenario.project_a.project,
        entity_type="PROJECT_COVER",
        asset="cover.png",
        attributes={"type": "image/png"},
        size=10,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )
    anonymous = APIClient()
    url = f"/api/assets/v2/static/{cover.id}/"

    assert anonymous.get(url).status_code >= 400

    DeployBoard.objects.create(
        workspace=scenario.workspace,
        project=scenario.project_a.project,
        entity_name="project",
        entity_identifier=scenario.project_a.project.id,
        is_disabled=False,
    )

    assert anonymous.get(url).status_code == 302


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_naming_its_own_workspace_still_works(scenario):
    """Scoping must confine a token, not break it."""
    client, _ = _token_client(scenario.personas["member_a"], workspace=scenario.workspace)

    response = client.get(
        f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/issues/"
    )

    assert response.status_code == 200
    assert scenario.project_a.canary in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unscoped_token_keeps_its_previous_reach(scenario):
    """Tokens minted through the product leave workspace null.

    Their boundary stays the caller's memberships, so existing integrations are
    unaffected by the scoping rule.
    """
    client, _ = _token_client(scenario.personas["member_a"])

    response = client.get(
        f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/issues/"
    )

    assert response.status_code == 200
