# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Page, Project, ProjectMember, ProjectPage


@pytest.mark.contract
@pytest.mark.django_db
def test_page_duplicate_links_copy_only_to_authorized_route_project(
    session_client,
    workspace,
    create_user,
):
    authorized_project = Project.objects.create(
        name="Authorized project",
        identifier=f"A{uuid4().hex[:4]}",
        workspace=workspace,
    )
    foreign_project = Project.objects.create(
        name="Foreign project",
        identifier=f"F{uuid4().hex[:4]}",
        workspace=workspace,
    )
    ProjectMember.objects.create(
        project=authorized_project,
        workspace=workspace,
        member=create_user,
        role=15,
        is_active=True,
    )
    source = Page.objects.create(
        name="Shared source",
        workspace=workspace,
        owned_by=create_user,
        access=Page.PUBLIC_ACCESS,
    )
    ProjectPage.objects.bulk_create(
        [
            ProjectPage(
                page=source,
                project=authorized_project,
                workspace=workspace,
            ),
            ProjectPage(
                page=source,
                project=foreign_project,
                workspace=workspace,
            ),
        ]
    )

    with (
        mock.patch("plane.app.views.page.base.page_transaction.delay"),
        mock.patch("plane.app.views.page.base.copy_s3_objects_of_description_and_assets.delay") as copy_assets,
    ):
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/{authorized_project.id}/pages/{source.id}/duplicate/",
            {},
            format="json",
        )

    assert response.status_code == status.HTTP_201_CREATED
    duplicate_id = response.data["id"]
    assert set(
        ProjectPage.objects.filter(page_id=duplicate_id).values_list(
            "project_id",
            flat=True,
        )
    ) == {authorized_project.id}
    copy_assets.assert_called_once()
    assert copy_assets.call_args.kwargs["project_id"] == authorized_project.id
