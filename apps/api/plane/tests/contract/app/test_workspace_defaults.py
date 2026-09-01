# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace home defaults and shared quick links.

The interesting cases are not the happy paths. They are: that seeding beats
upstream's lazy seed rather than racing it, that the destructive option's blast
radius is the keys an administrator actually chose, that a workspace admin
cannot reach a workspace they do not administer, and that hiding a shared link
is available to people who are not administrators -- otherwise "people can still
adjust" is untrue for almost everyone.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import User, Workspace, WorkspaceHomePreference, WorkspaceMember
from plane.ext.models import (
    WorkspaceDefaultsAdoption,
    WorkspaceHomeDefault,
    WorkspaceSharedLink,
    WorkspaceSharedLinkHide,
)

ADMIN = 20
MEMBER = 15
GUEST = 5


def _user(email):
    return User.objects.create(email=email, username=uuid.uuid4().hex)


def _workspace(owner, slug="acme"):
    workspace = Workspace.objects.create(name=slug, slug=slug, owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=ADMIN)
    return workspace


def _join(workspace, user, role=MEMBER):
    return WorkspaceMember.objects.create(workspace=workspace, member=user, role=role)


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _defaults_url(slug):
    return f"/api/workspaces/{slug}/home-defaults/"


def _links_url(slug):
    return f"/api/workspaces/{slug}/shared-links/"


@pytest.fixture
def workspace(db):
    return _workspace(_user("owner@acme.example"))


@pytest.fixture
def admin_client(workspace):
    return _client(workspace.owner)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_administrator_sets_the_default_layout(admin_client, workspace):
    response = admin_client.patch(
        _defaults_url(workspace.slug),
        {"defaults": [{"key": "quick_links", "is_enabled": True, "sort_order": 1}]},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert WorkspaceHomeDefault.objects.filter(workspace=workspace, key="quick_links").exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unknown_widget_is_refused(admin_client, workspace):
    response = admin_client.patch(_defaults_url(workspace.slug), {"defaults": [{"key": "invented"}]}, format="json")

    assert response.status_code == 400
    assert "available_keys" in response.json()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_may_read_but_not_change_the_defaults(workspace):
    member = _user("member@acme.example")
    _join(workspace, member)
    client = _client(member)

    assert client.get(_defaults_url(workspace.slug)).status_code == 200
    assert client.patch(_defaults_url(workspace.slug), {"defaults": []}, format="json").status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_an_administrator_of_another_workspace_is_refused(workspace):
    """Cross-workspace is the mistake that actually ships."""
    outsider = _user("admin@other.example")
    _workspace(outsider, slug="other")

    response = _client(outsider).patch(_defaults_url(workspace.slug), {"defaults": []}, format="json")

    assert response.status_code in (403, 404)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_new_member_is_seeded_before_any_home_request(admin_client, workspace):
    """Proves the signal beats upstream's lazy seed rather than racing it."""
    admin_client.patch(
        _defaults_url(workspace.slug),
        {"defaults": [{"key": "recents", "is_enabled": False, "sort_order": 3}]},
        format="json",
    )

    joiner = _user("joiner@acme.example")
    _join(workspace, joiner)

    preference = WorkspaceHomePreference.objects.filter(workspace=workspace, user=joiner, key="recents").first()
    assert preference is not None, "the rows must exist before the browser asks"
    assert preference.is_enabled is False
    assert WorkspaceDefaultsAdoption.objects.filter(workspace=workspace, user=joiner).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_seeding_never_overwrites_a_choice_somebody_made(admin_client, workspace):
    member = _user("early@acme.example")
    _join(workspace, member)
    WorkspaceHomePreference.objects.update_or_create(
        workspace=workspace, user=member, key="recents", defaults={"is_enabled": True}
    )

    admin_client.patch(
        _defaults_url(workspace.slug),
        {"defaults": [{"key": "recents", "is_enabled": False}]},
        format="json",
    )

    assert WorkspaceHomePreference.objects.get(workspace=workspace, user=member, key="recents").is_enabled is True, (
        "apply-to-new-members-only must leave existing people alone"
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_applying_to_everyone_replaces_the_managed_keys(admin_client, workspace):
    member = _user("existing@acme.example")
    _join(workspace, member)
    WorkspaceHomePreference.objects.update_or_create(
        workspace=workspace, user=member, key="recents", defaults={"is_enabled": True}
    )

    response = admin_client.patch(
        _defaults_url(workspace.slug),
        {"defaults": [{"key": "recents", "is_enabled": False}], "apply_to_everyone": True},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert WorkspaceHomePreference.objects.get(workspace=workspace, user=member, key="recents").is_enabled is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_key_the_defaults_do_not_mention_survives_applying_to_everyone(admin_client, workspace):
    """The blast radius is the layout the administrator chose, not the whole page."""
    member = _user("tidy@acme.example")
    _join(workspace, member)
    WorkspaceHomePreference.objects.update_or_create(
        workspace=workspace, user=member, key="my_stickies", defaults={"is_enabled": False}
    )

    admin_client.patch(
        _defaults_url(workspace.slug),
        {"defaults": [{"key": "recents", "is_enabled": True}], "apply_to_everyone": True},
        format="json",
    )

    assert WorkspaceHomePreference.objects.get(workspace=workspace, user=member, key="my_stickies").is_enabled is False


@pytest.mark.contract
@pytest.mark.django_db
def test_an_administrator_shares_a_link_and_everyone_sees_it(admin_client, workspace):
    created = admin_client.post(
        _links_url(workspace.slug), {"title": "Runbook", "url": "wiki.acme.example/runbook"}, format="json"
    )
    assert created.status_code == 201, created.content
    assert created.json()["url"].startswith("http://")

    member = _user("reader@acme.example")
    _join(workspace, member)

    listed = _client(member).get(_links_url(workspace.slug)).json()
    assert [link["title"] for link in listed] == ["Runbook"]
    assert listed[0]["is_hidden"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_javascript_url_is_refused(admin_client, workspace):
    response = admin_client.post(
        _links_url(workspace.slug), {"title": "x", "url": "javascript:alert(1)"}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_may_hide_a_shared_link_and_bring_it_back(admin_client, workspace):
    """'People can still adjust' must not be accidentally admin-gated."""
    link_id = admin_client.post(
        _links_url(workspace.slug), {"title": "Runbook", "url": "https://wiki.acme.example"}, format="json"
    ).json()["id"]

    member = _user("hider@acme.example")
    _join(workspace, member)
    client = _client(member)
    hide_url = f"{_links_url(workspace.slug)}{link_id}/hide/"

    assert client.post(hide_url).status_code == 204
    assert client.get(_links_url(workspace.slug)).json()[0]["is_hidden"] is True

    assert client.delete(hide_url).status_code == 204
    assert client.get(_links_url(workspace.slug)).json()[0]["is_hidden"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_hiding_is_personal(admin_client, workspace):
    link_id = admin_client.post(
        _links_url(workspace.slug), {"title": "Runbook", "url": "https://wiki.acme.example"}, format="json"
    ).json()["id"]

    member = _user("one@acme.example")
    other = _user("two@acme.example")
    _join(workspace, member)
    _join(workspace, other)

    _client(member).post(f"{_links_url(workspace.slug)}{link_id}/hide/")

    assert _client(other).get(_links_url(workspace.slug)).json()[0]["is_hidden"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_may_not_edit_or_remove_a_shared_link(admin_client, workspace):
    link_id = admin_client.post(
        _links_url(workspace.slug), {"title": "Runbook", "url": "https://wiki.acme.example"}, format="json"
    ).json()["id"]

    member = _user("nosy@acme.example")
    _join(workspace, member)
    client = _client(member)
    detail = f"{_links_url(workspace.slug)}{link_id}/"

    assert client.patch(detail, {"url": "https://evil.example"}, format="json").status_code == 403
    assert client.delete(detail).status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_editing_a_shared_link_reaches_everyone(admin_client, workspace):
    """The reason these are shared rather than copied."""
    link_id = admin_client.post(
        _links_url(workspace.slug), {"title": "Runbook", "url": "https://wiki.acme.example/typo"}, format="json"
    ).json()["id"]

    member = _user("later@acme.example")
    _join(workspace, member)

    admin_client.patch(
        f"{_links_url(workspace.slug)}{link_id}/", {"url": "https://wiki.acme.example/runbook"}, format="json"
    )

    assert _client(member).get(_links_url(workspace.slug)).json()[0]["url"] == "https://wiki.acme.example/runbook"


@pytest.mark.contract
@pytest.mark.django_db
def test_removing_a_shared_link_removes_it_for_everyone(admin_client, workspace):
    link_id = admin_client.post(
        _links_url(workspace.slug), {"title": "Dead service", "url": "https://gone.acme.example"}, format="json"
    ).json()["id"]

    member = _user("survivor@acme.example")
    _join(workspace, member)

    admin_client.delete(f"{_links_url(workspace.slug)}{link_id}/")

    assert _client(member).get(_links_url(workspace.slug)).json() == []


@pytest.mark.contract
@pytest.mark.django_db
def test_a_guest_may_hide_a_shared_link(admin_client, workspace):
    link_id = admin_client.post(
        _links_url(workspace.slug), {"title": "Runbook", "url": "https://wiki.acme.example"}, format="json"
    ).json()["id"]

    guest = _user("guest@acme.example")
    _join(workspace, guest, role=GUEST)

    assert _client(guest).post(f"{_links_url(workspace.slug)}{link_id}/hide/").status_code == 204
    assert WorkspaceSharedLinkHide.objects.filter(user=guest).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_a_workspace_with_no_defaults_seeds_nothing(workspace):
    """Upstream's own lazy seed still runs, which is what such a workspace wants."""
    joiner = _user("plain@acme.example")
    _join(workspace, joiner)

    assert WorkspaceHomePreference.objects.filter(workspace=workspace, user=joiner).count() == 0
    assert not WorkspaceDefaultsAdoption.objects.filter(workspace=workspace, user=joiner).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_link_belonging_to_another_workspace_is_not_reachable(admin_client, workspace):
    outsider = _user("other-owner@other.example")
    other = _workspace(outsider, slug="other-ws")
    link = WorkspaceSharedLink.objects.create(workspace=other, title="Theirs", url="https://other.example")

    response = admin_client.delete(f"{_links_url(workspace.slug)}{link.id}/")

    assert response.status_code == 404
    assert WorkspaceSharedLink.objects.filter(pk=link.id).exists()
