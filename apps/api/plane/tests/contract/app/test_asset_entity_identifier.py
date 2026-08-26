# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An unusable entity identifier must say so.

A client that sends one because the record it names does not exist yet — the
project-creation form picking a cover before the project is saved — used to get
"Please provide valid detail", the generic answer for any Django ValidationError
that escaped a view. Nothing in it identified the field, so the failure read as a
server fault.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import FileAsset, Project, ProjectMember, User, Workspace, WorkspaceMember

URL = "/api/assets/v2/workspaces/acme/"


@pytest.fixture
def member(db):
    user = User.objects.create(email="person@corp.com", username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(name="Acme", slug="acme", owner=user)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20, is_active=True)
    project = Project.objects.create(name="Platform", identifier="PLAT", workspace=workspace, created_by=user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=user, role=20, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, project


def _upload(client, **extra):
    return client.post(
        URL,
        {
            "entity_type": FileAsset.EntityTypeContext.PROJECT_COVER,
            "name": "cover.png",
            "size": 2014337,
            "type": "image/png",
            **extra,
        },
        format="json",
    )


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("identifier", ["", "not-a-uuid", "123"])
def test_an_identifier_that_is_not_an_id_names_the_field(member, identifier):
    client, _ = member

    response = _upload(client, entity_identifier=identifier)

    assert response.status_code == 400
    assert "entity_identifier" in response.data["error"]
    assert "Please provide valid detail" not in str(response.data)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_missing_identifier_still_reports_an_unknown_target(member):
    """Absent is different from malformed: nothing was named at all."""
    client, _ = member

    response = _upload(client)

    assert response.status_code == 404


@pytest.mark.contract
@pytest.mark.django_db
def test_a_real_project_still_uploads(member):
    """The positive control, so the guard cannot pass by refusing everything."""
    client, project = member

    response = _upload(client, entity_identifier=str(project.id))

    assert response.status_code == 200
    assert response.data["asset_id"]
