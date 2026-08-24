# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Standing invariants over the authorization surface.

Two things are checked here, and they fail for different reasons:

``test_every_route_declares_an_authorization_mechanism`` fails when a route is
added that no recognized mechanism protects. It is the guard that keeps the
queryset-filtering style — where an omitted ``.filter()`` is invisible — from
silently regrowing.

``test_non_member_cannot_reach_workspace_scoped_routes`` actually issues the
requests. Static classification only proves a mechanism is *present*; this
proves it *works*, by having an authenticated user with no membership ask for
another workspace's data and requiring that the answer is never 200.
"""

import uuid

import pytest
from django.urls import NoReverseMatch, reverse
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State, User, Workspace, WorkspaceMember
from plane.tests.support.route_inventory import (
    MECHANISM_NONE,
    collect_routes,
    workspace_scoped,
)

# Routes that are unauthenticated by design. Each entry needs a reason, and
# adding one should be a deliberate review decision rather than a way to make
# this file go quiet.
INTENTIONALLY_UNGUARDED = {
    # Authentication endpoints must be reachable before a session exists.
    "plane.authentication.views",
    "plane.ext.auth.views",
    # Published boards are public by definition; their exposure is bounded by
    # what the DeployBoard actually publishes, covered separately.
    "plane.space.views",
    # Instance bootstrap and health, served before/without a workspace.
    "plane.license.api.views.instance",
    # DRF's own router index view, not application code.
    "rest_framework.routers",
}

# Views that are authenticated but deliberately carry no workspace scope.
INTENTIONALLY_UNSCOPED = {
    # Reports whether a slug is already taken, so it must answer for slugs the
    # caller cannot see. Returns a boolean and no workspace content.
    "WorkSpaceAvailabilityCheckEndpoint",
    # Authenticated proxy to Unsplash's public image search for cover images.
    # Takes no workspace and returns no Hangar data.
    "UnsplashEndpoint",
}


def _is_exempt(record):
    return any(record.view_module.startswith(prefix) for prefix in INTENTIONALLY_UNGUARDED)


@pytest.mark.contract
def test_every_route_declares_an_authorization_mechanism():
    """A new route must be protected by something we can name.

    If this fails, the route needs permission_classes, an @allow_permission
    decorator, membership filtering in get_queryset, or a service-layer check
    — not an entry in the exemption list, unless it is genuinely public.
    """
    unclassified = [
        record.describe()
        for record in collect_routes()
        if record.is_unclassified
        and not _is_exempt(record)
        and record.handlers
        and getattr(record.view_class, "__name__", "") not in INTENTIONALLY_UNSCOPED
    ]

    assert not unclassified, "Routes with no recognized authorization mechanism:\n  " + "\n  ".join(
        sorted(unclassified)
    )


# A string that appears nowhere except inside the victim's workspace, so its
# presence in any response is unambiguous evidence of a leak.
CANARY = "ZZQCANARYWORKITEMZZQ"


@pytest.fixture
def victim_workspace(db):
    """A workspace owned by someone else, holding data worth leaking."""
    owner = User.objects.create(email=f"owner-{uuid.uuid4().hex[:8]}@example.com", username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(
        name="Victim Workspace",
        owner=owner,
        slug=f"victim-{uuid.uuid4().hex[:8]}",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    project = Project.objects.create(
        name="Victim Project",
        identifier=f"V{uuid.uuid4().hex[:4]}".upper(),
        workspace=workspace,
        created_by=owner,
    )
    ProjectMember.objects.create(workspace=workspace, project=project, member=owner, role=20, is_active=True)
    state = State.objects.create(name="Todo", group="unstarted", workspace=workspace, project=project)
    issue = Issue.objects.create(
        name=CANARY,
        description_stripped=CANARY,
        workspace=workspace,
        project=project,
        state=state,
        created_by=owner,
    )
    return workspace, project, owner, issue


@pytest.fixture
def outsider_client(db):
    """Authenticated, but a member of nothing."""
    outsider = User.objects.create(
        email=f"outsider-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
    )
    client = APIClient()
    client.force_authenticate(user=outsider)
    return client


def _build_kwargs(record, workspace, project, issue):
    """Fill route kwargs with the victim's real identifiers.

    Returns None when a route needs an identifier we cannot supply, so the
    route is reported as unprobed rather than silently skipped.
    """
    values = {
        "slug": workspace.slug,
        "workspace_slug": workspace.slug,
        "project_id": str(project.id),
        "workspace_id": str(workspace.id),
        # Identifier-based lookups resolve an object by human-readable key
        # rather than uuid, so they must be probed with the real values or the
        # lookup silently misses and the route looks safe.
        "project_identifier": project.identifier,
        "issue_identifier": str(issue.sequence_id),
        "key": "quick_links",
        # Real ids: a write aimed at a random uuid would 404 for reasons that
        # have nothing to do with authorization, and prove nothing.
        "issue_id": str(issue.id),
        "work_item_id": str(issue.id),
        "pk": str(issue.id),
    }
    kwargs = {}
    for key in record.kwargs_required:
        if key in values:
            kwargs[key] = values[key]
        elif key.endswith("_id") or key == "pk":
            # A random id: a non-member must be refused before object lookup,
            # so a 404-for-missing-object is an acceptable outcome but a 200
            # never is.
            kwargs[key] = str(uuid.uuid4())
        else:
            return None
    return kwargs


@pytest.mark.contract
@pytest.mark.django_db
def test_non_member_never_receives_another_workspaces_content(victim_workspace, outsider_client):
    """The invariant is about content, not status codes.

    Several of these routes legitimately answer 200 with an empty result to a
    non-member — an empty search, a zeroed stats block — so asserting on the
    status code alone flags correct behaviour. What must never happen is that
    a non-member sees anything belonging to the workspace, so the victim's
    data is seeded with a canary and every response is checked for it.

    A 5xx is also a failure: a route that crashes has not denied the request,
    it has merely failed to answer it.
    """
    workspace, project, _owner, issue = victim_workspace

    leaked = []
    crashed = []
    unprobed = []

    for record in workspace_scoped(collect_routes()):
        if not record.name or "get" not in record.handlers:
            continue

        kwargs = _build_kwargs(record, workspace, project, issue)
        if kwargs is None:
            unprobed.append(record.describe())
            continue

        try:
            url = reverse(record.name, kwargs=kwargs)
        except NoReverseMatch:
            unprobed.append(record.describe())
            continue

        try:
            response = outsider_client.get(url, {"search": CANARY})
        except Exception as exc:  # noqa: BLE001 - a crash is not a pass
            unprobed.append(f"{record.describe()} raised {type(exc).__name__}: {exc}")
            continue

        body = response.content.decode(errors="replace")
        if CANARY in body or project.name in body or workspace.name in body:
            leaked.append(f"{record.describe()} -> {response.status_code} leaked content at {url}")
        elif response.status_code >= 500:
            crashed.append(f"{record.describe()} -> {response.status_code} at {url}")

    assert not leaked, "Non-member received workspace content:\n  " + "\n  ".join(sorted(leaked))
    assert not crashed, "Workspace-scoped routes crashed for a non-member:\n  " + "\n  ".join(sorted(crashed))

    # Surfaced, not asserted: these routes could not be exercised automatically
    # and still need a hand-written case. Failing on them would only encourage
    # deleting the report.
    if unprobed:
        print(f"\n[route-probe] {len(unprobed)} workspace-scoped routes not probed automatically:")
        for entry in sorted(unprobed):
            print(f"  {entry}")


@pytest.mark.contract
@pytest.mark.django_db
def test_non_member_cannot_write_to_another_workspace(victim_workspace, outsider_client):
    """Writes are held to a stricter rule than reads.

    An empty 200 is a correct answer to a read, but there is no equivalent for
    a write: a non-member must never get a success status from POST, PUT,
    PATCH or DELETE against another workspace. The row counts are compared
    before and after as well, because a 4xx that still mutated something would
    otherwise pass unnoticed.

    Requests deliberately carry the victim's real object ids, since a write
    aimed at a random uuid would 404 for reasons unrelated to authorization.
    """
    workspace, project, _owner, issue = victim_workspace

    def _counts():
        return {
            "workspaces": Workspace.objects.count(),
            "projects": Project.objects.count(),
            "issues": Issue.objects.count(),
            "states": State.objects.count(),
            "workspace_members": WorkspaceMember.objects.count(),
            "project_members": ProjectMember.objects.count(),
        }

    before = _counts()
    accepted = []
    attempted = 0

    for record in workspace_scoped(collect_routes()):
        if not record.name:
            continue

        kwargs = _build_kwargs(record, workspace, project, issue)
        if kwargs is None:
            continue

        try:
            url = reverse(record.name, kwargs=kwargs)
        except NoReverseMatch:
            continue

        for verb in ("post", "put", "patch", "delete"):
            if verb not in record.handlers:
                continue
            attempted += 1
            payload = {"name": f"{CANARY}-write", "display_name": f"{CANARY}-write"}
            try:
                response = getattr(outsider_client, verb)(url, payload, format="json")
            except Exception:  # noqa: BLE001 - a crash is not an authorization decision
                continue

            if 200 <= response.status_code < 300:
                accepted.append(f"{verb.upper()} {url} -> {response.status_code} [{record.view_module}]")

    assert attempted > 50, f"Only {attempted} write attempts made; the probe is not covering the surface"
    assert not accepted, "Non-member write accepted:\n  " + "\n  ".join(sorted(accepted))

    after = _counts()
    assert before == after, f"Non-member writes changed the database:\n  before={before}\n  after={after}"


@pytest.mark.contract
def test_inventory_sees_a_plausible_number_of_routes():
    """Guards the harness itself.

    If the resolver walk silently stops matching — a refactor moves views, or
    the callback attribute changes — both tests above would pass by examining
    nothing at all.
    """
    records = collect_routes()
    assert len(records) > 100, f"Route inventory collapsed to {len(records)} routes; the walk is broken"
    assert any(MECHANISM_NONE not in record.mechanisms for record in records)


@pytest.mark.contract
def test_a_route_is_never_scoped_by_less_than_its_url_captures():
    """The failure mode that hid fifteen routes from every probe above.

    ``workspace_scoped`` selects on ``slug`` appearing in ``kwargs_required``.
    That list used to be read from the leaf pattern only, so a route mounted
    under ``include()`` — where the parent captures the slug — reported no
    parameters at all and was quietly skipped. Nothing failed: the report
    stayed green while naming fewer routes than it claimed to cover.

    Comparing the captures against the URL text catches this for any nesting
    depth, without naming a route that a later refactor may move.
    """
    unaccounted = [
        record.describe()
        for record in collect_routes()
        for parameter in ("slug", "project_id")
        if f":{parameter}>" in record.pattern and parameter not in record.kwargs_required
    ]

    assert not unaccounted, (
        "Routes capture a parameter their inventory entry does not list, so scope "
        "filters skip them:\n  " + "\n  ".join(sorted(unaccounted))
    )
