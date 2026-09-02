# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A project's display name is prose; its identifier is a key.

Upstream held both to the same rule, one written for identifiers, which forbids
`- . ' & ( )` among others. Those characters are ordinary in the name of a real
project, and two things broke as a result: projects could not be created with
perfectly reasonable names, and duplication could not work at all, because the
modal prefills "<source> (Copy)" and parentheses were forbidden.

The identifier keeps the strict rule. It becomes part of a work-item key and a
URL, so it has to.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import Project, ProjectMember, User, Workspace, WorkspaceMember

ADMIN = 20


def _user(email):
    return User.objects.create(email=email, username=uuid.uuid4().hex)


@pytest.fixture
def workspace(db):
    owner = _user("owner@acme.example")
    workspace = Workspace.objects.create(name="acme", slug="acme", owner=owner)
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=ADMIN)
    return workspace


@pytest.fixture
def client(workspace):
    api = APIClient()
    api.force_authenticate(user=workspace.owner)
    return api


def _create(client, slug, **overrides):
    body = {"name": "Plain Project", "identifier": "PLAIN"}
    body.update(overrides)
    return client.post(f"/api/workspaces/{slug}/projects/", body, format="json")


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "Pentest - Client X",
        "Q3 2026 (Phase 1)",
        "v1.0",
        "Client's audit",
        "Web & API",
        "Report: findings",
        "100% coverage",
    ],
)
def test_an_ordinary_project_name_is_accepted(client, workspace, name):
    """Each of these was refused before, which is why projects could not be made."""
    response = _create(client, workspace.slug, name=name, identifier=uuid.uuid4().hex[:8].upper())

    assert response.status_code == 201, response.content
    assert Project.objects.filter(workspace=workspace, name=name).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_name_carrying_a_line_break_is_refused(client, workspace):
    response = _create(client, workspace.slug, name="One line\nTwo lines")

    assert response.status_code == 400
    assert "PROJECT_NAME_CANNOT_CONTAIN_SPECIAL_CHARACTERS" in str(response.content)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_name_carrying_a_bidirectional_override_is_refused(client, workspace):
    """A name is rendered beside other people's; it must not reorder them."""
    response = _create(client, workspace.slug, name="Report‮")

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_an_overlong_name_is_refused(client, workspace):
    response = _create(client, workspace.slug, name="x" * 256)

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("identifier", ["PR-1", "PR.1", "PR(1)", "PR&1"])
def test_the_identifier_still_refuses_punctuation(client, workspace, identifier):
    """It becomes part of a work-item key and a URL, so it stays strict."""
    response = _create(client, workspace.slug, identifier=identifier)

    assert response.status_code == 400
    assert "PROJECT_IDENTIFIER_CANNOT_CONTAIN_SPECIAL_CHARACTERS" in str(response.content)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_duplicate_accepts_the_name_its_own_modal_prefills(client, workspace):
    """The regression that made duplication fail every single time.

    `duplicate-project-modal.tsx` prefills "<source> (Copy)". Parentheses were
    forbidden, so the modal's own default value was rejected by the endpoint it
    submits to, and no duplication from the interface could ever succeed.
    """
    source = Project.objects.create(
        name="Client Audit", identifier="AUDIT", workspace=workspace, created_by=workspace.owner
    )
    ProjectMember.objects.create(project=source, member=workspace.owner, role=ADMIN)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{source.id}/duplicate/",
        {"name": "Client Audit (Copy)", "identifier": "AUDIT2"},
        format="json",
    )

    assert response.status_code == 201, response.content
    assert Project.objects.filter(workspace=workspace, name="Client Audit (Copy)").exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_duplicate_still_refuses_a_control_character_in_the_name(client, workspace):
    source = Project.objects.create(
        name="Client Audit", identifier="AUDIT", workspace=workspace, created_by=workspace.owner
    )
    ProjectMember.objects.create(project=source, member=workspace.owner, role=ADMIN)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/projects/{source.id}/duplicate/",
        {"name": "Client Audit‮", "identifier": "AUDIT2"},
        format="json",
    )

    assert response.status_code == 400
