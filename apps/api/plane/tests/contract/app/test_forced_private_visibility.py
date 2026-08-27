# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An instance can refuse to let anything be seen beyond its members.

Hangar is deployed where the interesting question is not who may edit something
but who may read it. Plane creates a page public, creates a view public, and
lets anyone who can administer a project publish it to the internet.

A project's own network setting is left alone: it decides whether members of a
workspace can discover a project they have not been added to, not whether
outsiders can read it.

Where the policy is on, those choices are not offered and not accepted, and the
public surface is closed outright. The refusal is at the single point every
public request passes through, rather than in each view, because a view that
forgot the check would serve exactly what the instance said must not be served.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import DeployBoard, Page, Project, ProjectMember, User, Workspace, WorkspaceMember
from plane.db.models.view import IssueView
from plane.license.models import InstanceConfiguration
from plane.utils.visibility_policy import (
    FORCE_PRIVATE_VISIBILITY_KEY,
    apply_private_visibility,
    PAGE_PRIVATE_ACCESS,
    VIEW_PRIVATE_ACCESS,
)


@pytest.fixture
def member(db):
    user = User.objects.create(email="person@corp.com", username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(name="Acme", slug="acme", owner=user)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20, is_active=True)
    project = Project.objects.create(name="Platform", identifier="PLAT", workspace=workspace, created_by=user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=user, role=20, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, workspace, project, user


def _policy(value):
    InstanceConfiguration.objects.update_or_create(
        key=FORCE_PRIVATE_VISIBILITY_KEY,
        defaults={"value": value, "category": "VISIBILITY", "is_encrypted": False},
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_the_public_surface_is_closed(member):
    _policy("1")
    _, _, project, _ = member

    response = APIClient().get(f"/api/public/anchor/{uuid.uuid4().hex}/settings/")

    assert response.status_code in (403, 404)


@pytest.mark.contract
@pytest.mark.django_db
def test_publishing_a_project_is_refused(member):
    _policy("1")
    client, workspace, project, owner = member

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/project-deploy-boards/",
        {},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
def test_with_the_policy_off_nothing_changes(member):
    """The policy is a decision an operator makes, not the only way to run this."""
    _policy("0")
    client, workspace, project, owner = member

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/project-deploy-boards/",
        {},
        format="json",
    )

    assert response.status_code != 403


@pytest.mark.contract
@pytest.mark.django_db
def test_a_page_asked_for_publicly_is_created_private(member):
    _policy("1")
    client, workspace, project, owner = member

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/",
        {"name": "Notes", "access": 0},
        format="json",
    )

    assert response.status_code == 201
    assert Page.objects.get(id=response.data["id"]).access == PAGE_PRIVATE_ACCESS


@pytest.mark.contract
@pytest.mark.django_db
def test_a_view_asked_for_publicly_is_created_private(member):
    """Page and IssueView number these the opposite way round.

    A single "private" value applied to both would publish one of them, which is
    why the policy names one constant per model.
    """
    _policy("1")
    client, workspace, project, owner = member

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{project.id}/views/",
        {"name": "Everything", "access": 1},
        format="json",
    )

    assert response.status_code == 201
    assert IssueView.objects.get(id=response.data["id"]).access == VIEW_PRIVATE_ACCESS


@pytest.mark.contract
@pytest.mark.django_db
def test_objects_that_already_existed_are_brought_into_line(member):
    """Enforcing at write time governs only what happens next.

    Without this an operator turns the policy on, is told it was saved, and every
    project, page and published board created beforehand stays exactly as
    visible as it was.
    """
    client, workspace, project, owner = member
    page = Page.objects.create(name="Notes", workspace=workspace, access=0, owned_by=owner)
    view = IssueView.objects.create(name="All", workspace=workspace, project=project, access=1, owned_by=owner)
    board = DeployBoard.objects.create(
        entity_name="project", entity_identifier=project.id, project=project, workspace=workspace
    )

    changed = apply_private_visibility()

    project.refresh_from_db()
    page.refresh_from_db()
    view.refresh_from_db()
    board.refresh_from_db()
    assert page.access == PAGE_PRIVATE_ACCESS
    assert view.access == VIEW_PRIVATE_ACCESS
    assert board.is_disabled is True
    assert changed["deploy_boards"] == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_a_published_board_is_disabled_rather_than_deleted(member):
    """The row carries the anchor that was handed out.

    Deleting it would let the same address be reissued later for something else,
    so an old link would start resolving to content nobody meant to attach to it.
    """
    _, workspace, project, owner = member
    board = DeployBoard.objects.create(
        entity_name="project", entity_identifier=project.id, project=project, workspace=workspace
    )
    anchor = board.anchor

    apply_private_visibility()

    assert DeployBoard.objects.filter(anchor=anchor).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_running_it_twice_changes_nothing_the_second_time(member):
    """Saving the God Mode page again must not cost a full table rewrite."""
    _, workspace, project, owner = member
    Page.objects.create(name="Notes", workspace=workspace, access=0, owned_by=owner)

    apply_private_visibility()
    second = apply_private_visibility()

    assert second == {"pages": 0, "views": 0, "deploy_boards": 0}
