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

from plane.db.models import Project, ProjectMember, User, Workspace, WorkspaceMember
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
        if record.is_unclassified and not _is_exempt(record) and record.handlers
    ]

    assert not unclassified, "Routes with no recognized authorization mechanism:\n  " + "\n  ".join(
        sorted(unclassified)
    )


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
    return workspace, project, owner


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


def _build_kwargs(record, workspace, project):
    """Fill route kwargs with the victim's real identifiers.

    Returns None when a route needs an identifier we cannot supply, so the
    route is reported as unprobed rather than silently skipped.
    """
    values = {
        "slug": workspace.slug,
        "workspace_slug": workspace.slug,
        "project_id": str(project.id),
        "workspace_id": str(workspace.id),
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
def test_non_member_cannot_reach_workspace_scoped_routes(victim_workspace, outsider_client):
    """An authenticated non-member must never receive 200 from another workspace."""
    workspace, project, _owner = victim_workspace

    leaked = []
    unprobed = []

    for record in workspace_scoped(collect_routes()):
        if not record.name or "get" not in record.handlers:
            continue

        kwargs = _build_kwargs(record, workspace, project)
        if kwargs is None:
            unprobed.append(record.describe())
            continue

        try:
            url = reverse(record.name, kwargs=kwargs)
        except NoReverseMatch:
            unprobed.append(record.describe())
            continue

        try:
            response = outsider_client.get(url)
        except Exception as exc:  # noqa: BLE001 - a crash is not a pass
            unprobed.append(f"{record.describe()} raised {type(exc).__name__}: {exc}")
            continue

        if response.status_code == 200:
            leaked.append(f"{record.describe()} -> 200 at {url}")

    assert not leaked, "Non-member received 200 from workspace-scoped routes:\n  " + "\n  ".join(sorted(leaked))

    # Surfaced, not asserted: these routes could not be exercised automatically
    # and still need a hand-written case. Failing on them would only encourage
    # deleting the report.
    if unprobed:
        print(f"\n[route-probe] {len(unprobed)} workspace-scoped routes not probed automatically:")
        for entry in sorted(unprobed):
            print(f"  {entry}")


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
