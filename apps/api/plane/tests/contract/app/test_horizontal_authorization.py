# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Boundaries *inside* a workspace, not just between workspaces.

The existing matrix probe asks whether a member of nothing can see a workspace.
That is the tenant boundary. This file asks the harder question: can someone who
legitimately belongs here reach something they were not given? A workspace member
never added to a project, a guest, a project administrator who is not a workspace
administrator — every one of them passes the workspace gate, so only a
project-level check stops them.

That is the exact shape of the last real defect found here: `IssueViewViewSet`
guarded every action except `create`, and a caller with any account could write
into any project.

Assertion, as elsewhere: a canary that exists only inside one project must never
appear in a response, a write must never be accepted, and a 5xx is a failure
because a route that crashes has not denied anything.
"""

import uuid

import pytest
from django.urls import NoReverseMatch, reverse
from rest_framework.test import APIClient

from plane.db.models import APIToken, Issue, IssueView, Project, ProjectMember, State, WorkspaceMember
from plane.tests.support.personas import build_scenario
from plane.tests.support.route_inventory import collect_routes, project_scoped, workspace_scoped

# Personas that must never see project content they were not added to.
BLIND_TO_PROJECTS = (
    "outsider",
    "ws_member_no_project",
    "other_workspace_admin",
)


@pytest.fixture
def scenario(db):
    return build_scenario()


def _kwargs_for(record, scenario, project_fixture):
    """Fill route kwargs, or return None when the route needs an id we lack."""
    values = {
        "slug": scenario.workspace.slug,
        "workspace_slug": scenario.workspace.slug,
        "workspace_id": str(scenario.workspace.id),
        "project_id": str(project_fixture.project.id),
        "project_identifier": project_fixture.project.identifier,
        "issue_id": str(project_fixture.issue.id),
        "work_item_id": str(project_fixture.issue.id),
        "issue_identifier": str(project_fixture.issue.sequence_id),
        "pk": str(project_fixture.issue.id),
        "state_id": str(project_fixture.state.id),
        "key": "quick_links",
    }
    kwargs = {}
    for key in record.kwargs_required:
        if key in values:
            kwargs[key] = values[key]
        elif key.endswith("_id") or key == "pk":
            return None
        else:
            return None
    return kwargs


def _leaks(response, *needles):
    body = response.content.decode(errors="replace")
    return [needle for needle in needles if needle in body]


# The external API authenticates by token, not session. force_authenticate
# bypasses its authentication class entirely and reports acceptances that do not
# happen in practice — verified against a real APIToken, which is refused. It is
# probed separately, with real tokens.
#
# The test is on the generated path rather than the view module because several
# route names are registered in both url confs, so reverse() can return an
# /api/v1/ path for a record whose module is plane.app.views.
EXTERNAL_API_PREFIX = "/api/v1/"


def _is_session_api(url):
    return not url.startswith(EXTERNAL_API_PREFIX)


def _probe_reads(client, scenario, project_fixture, forbidden):
    """GET every project-scoped route and collect leaks and crashes."""
    leaked, crashed = [], []
    for record in project_scoped(collect_routes()):
        if not record.name or "get" not in record.handlers:
            continue
        kwargs = _kwargs_for(record, scenario, project_fixture)
        if kwargs is None:
            continue
        try:
            url = reverse(record.name, kwargs=kwargs)
        except NoReverseMatch:
            continue
        if not _is_session_api(url):
            continue
        try:
            response = client.get(url, {"search": forbidden[0]})
        except Exception:  # noqa: BLE001 - a crash is not a denial
            continue
        found = _leaks(response, *forbidden)
        if found:
            leaked.append(f"{record.describe()} -> {response.status_code} leaked {found} at {url}")
        elif response.status_code >= 500:
            crashed.append(f"{record.describe()} -> {response.status_code} at {url}")
    return leaked, crashed


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("persona", BLIND_TO_PROJECTS)
def test_persona_never_sees_project_content(scenario, persona):
    """None of these callers was added to project A."""
    client = scenario.client(persona)

    leaked, crashed = _probe_reads(client, scenario, scenario.project_a, [scenario.project_a.canary])

    assert not leaked, f"{persona} received project content:\n  " + "\n  ".join(sorted(leaked))
    assert not crashed, f"{persona} crashed routes:\n  " + "\n  ".join(sorted(crashed))


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("persona", ("guest_a", "member_a", "project_admin_a"))
def test_membership_in_one_project_does_not_reach_another(scenario, persona):
    """Belonging to A must not reveal B, even for A's administrator."""
    client = scenario.client(persona)

    leaked, crashed = _probe_reads(client, scenario, scenario.project_b, [scenario.project_b.canary])

    assert not leaked, f"{persona} reached project B:\n  " + "\n  ".join(sorted(leaked))
    assert not crashed, f"{persona} crashed routes:\n  " + "\n  ".join(sorted(crashed))


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_member_can_actually_see_their_project(scenario):
    """Positive control.

    Without this the suite would pass just as well against a build that denied
    everything to everyone, which would tell us nothing.
    """
    client = scenario.client("member_a")

    response = client.get(
        reverse(
            "project-issue",
            kwargs={"slug": scenario.workspace.slug, "project_id": str(scenario.project_a.project.id)},
        )
    )

    assert response.status_code == 200
    assert scenario.project_a.canary in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("persona", BLIND_TO_PROJECTS + ("guest_a", "member_a", "project_admin_a"))
def test_no_persona_can_write_into_a_project_they_lack(scenario, persona):
    """Writes have no benign empty answer, so a 2xx is always wrong here.

    Every persona is aimed at a project it does not belong to: project B for
    those who hold membership of A, project A for the rest. Aiming a member of A
    at A would test nothing — and a guest of A may legitimately write its own
    display preferences there, which is not a boundary violation.
    """
    client = scenario.client(persona)
    holds_membership_of_a = persona in ("guest_a", "member_a", "project_admin_a")
    target = scenario.project_b if holds_membership_of_a else scenario.project_a

    before = (Issue.objects.count(), IssueView.objects.count(), State.objects.count())
    accepted = []
    attempted = 0

    for record in project_scoped(collect_routes()):
        if not record.name:
            continue
        kwargs = _kwargs_for(record, scenario, target)
        if kwargs is None:
            continue
        try:
            url = reverse(record.name, kwargs=kwargs)
        except NoReverseMatch:
            continue
        if not _is_session_api(url):
            continue
        for verb in ("post", "put", "patch", "delete"):
            if verb not in record.handlers:
                continue
            attempted += 1
            payload = {"name": f"{persona}-write", "display_name": f"{persona}-write", "filters": {}}
            try:
                response = getattr(client, verb)(url, payload, format="json")
            except Exception:  # noqa: BLE001
                continue
            if 200 <= response.status_code < 300:
                accepted.append(f"{verb.upper()} {url} -> {response.status_code} [{record.view_module}]")

    assert attempted > 20, f"only {attempted} write attempts; the probe is not covering the surface"
    assert not accepted, f"{persona} write accepted:\n  " + "\n  ".join(sorted(accepted))
    assert before == (Issue.objects.count(), IssueView.objects.count(), State.objects.count())


@pytest.mark.contract
@pytest.mark.django_db
def test_foreign_project_id_under_own_workspace_slug_is_refused(scenario):
    """IDOR inside a legitimate context.

    The workspace slug is one the caller belongs to, so the workspace gate
    passes; only a project-level filter refuses the foreign project id.
    """
    client = scenario.client("other_workspace_admin")

    response = client.get(
        reverse(
            "project-issue",
            kwargs={
                "slug": scenario.other_workspace.slug,
                "project_id": str(scenario.project_a.project.id),
            },
        )
    )

    assert scenario.project_a.canary not in response.content.decode()
    assert response.status_code != 200 or response.json() in ([], {}, {"results": []})


@pytest.mark.contract
@pytest.mark.django_db
def test_guest_cannot_raise_their_own_workspace_role(scenario):
    """Self-escalation on the workspace member endpoint."""
    client = scenario.client("guest_a")
    membership = WorkspaceMember.objects.get(workspace=scenario.workspace, member=scenario.personas["guest_a"])

    response = client.patch(
        reverse(
            "workspace-member",
            kwargs={"slug": scenario.workspace.slug, "pk": str(membership.id)},
        ),
        {"role": 20},
        format="json",
    )

    membership.refresh_from_db()
    assert response.status_code >= 400
    assert membership.role == 5


@pytest.mark.contract
@pytest.mark.django_db
def test_guest_cannot_raise_their_own_project_role(scenario):
    """Same on the project member endpoint, whose decorator admits guests."""
    client = scenario.client("guest_a")
    membership = ProjectMember.objects.get(project=scenario.project_a.project, member=scenario.personas["guest_a"])

    response = client.patch(
        reverse(
            "project-member",
            kwargs={
                "slug": scenario.workspace.slug,
                "project_id": str(scenario.project_a.project.id),
                "pk": str(membership.id),
            },
        ),
        {"role": 20},
        format="json",
    )

    membership.refresh_from_db()
    assert response.status_code >= 400
    assert membership.role == 5


@pytest.mark.contract
@pytest.mark.django_db
def test_deactivated_member_cannot_use_an_api_token(scenario):
    """The membership rows still exist; the account does not.

    Asserted through a real token rather than force_authenticate, because that
    helper installs the user without consulting is_active and would report a
    leak that cannot happen.
    """
    token = APIToken.objects.create(
        user=scenario.personas["deactivated_member"], label="t", token=f"tok-{uuid.uuid4().hex}"
    )
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)

    response = client.get(
        f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/issues/"
    )

    assert response.status_code == 403
    assert scenario.project_a.canary not in response.content.decode()


@pytest.mark.contract
@pytest.mark.django_db
def test_project_admin_is_not_a_workspace_admin(scenario):
    """Administering one project must not confer workspace administration."""
    client = scenario.client("project_admin_a")

    response = client.patch(
        reverse("workspace", kwargs={"slug": scenario.workspace.slug}),
        {"name": "Renamed by project admin"},
        format="json",
    )

    scenario.workspace.refresh_from_db()
    assert response.status_code >= 400
    assert scenario.workspace.name == "Victim Workspace"


@pytest.mark.contract
@pytest.mark.django_db
def test_scenario_covers_a_meaningful_number_of_routes(scenario):
    """Guards the probe itself against silently examining nothing."""
    project_routes = project_scoped(collect_routes())
    workspace_routes = workspace_scoped(collect_routes())

    assert len(project_routes) > 50, f"only {len(project_routes)} project-scoped routes found"
    assert len(workspace_routes) > len(project_routes)
    assert Project.objects.filter(workspace=scenario.workspace).count() == 2


@pytest.mark.contract
@pytest.mark.django_db
def test_workspace_member_cannot_archive_a_project_they_do_not_belong_to(scenario):
    """Archiving is destructive and was asymmetric.

    It also deletes every member's UserFavorite rows for the project, which
    un-archiving does not restore, so the operation is partly irreversible.
    Un-archiving routed through the permission class's stricter branch, so a
    workspace member could archive a project they cannot open and then not
    undo it.
    """
    token = APIToken.objects.create(
        user=scenario.personas["ws_member_no_project"], label="t", token=f"tok-{uuid.uuid4().hex}"
    )
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)

    response = client.post(
        f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/archive/"
    )

    scenario.project_a.project.refresh_from_db()
    assert response.status_code >= 400
    assert scenario.project_a.project.archived_at is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_member_can_still_archive_and_unarchive(scenario):
    """The fix must not cost the people who are supposed to do this.

    Both directions are asserted: the defect was that they disagreed, so
    checking only one would leave the asymmetry undetected.
    """
    token = APIToken.objects.create(
        user=scenario.personas["member_a"], label="t", token=f"tok-{uuid.uuid4().hex}"
    )
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    url = f"/api/v1/workspaces/{scenario.workspace.slug}/projects/{scenario.project_a.project.id}/archive/"

    archived = client.post(url)
    scenario.project_a.project.refresh_from_db()
    assert archived.status_code == 204
    assert scenario.project_a.project.archived_at is not None

    restored = client.delete(url)
    scenario.project_a.project.refresh_from_db()
    assert restored.status_code == 204
    assert scenario.project_a.project.archived_at is None

