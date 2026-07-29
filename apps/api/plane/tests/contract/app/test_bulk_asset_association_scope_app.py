# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for ``ProjectBulkAssetEndpoint`` ownership scoping."""

from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import FileAsset, Project, ProjectMember, User


def bulk_asset_url(slug, project_id):
    return f"/api/assets/v2/workspaces/{slug}/projects/{project_id}/{project_id}/bulk/"


def create_cover_asset(*, workspace, created_by, project=None, name="cover.png"):
    asset = FileAsset(
        attributes={"name": name, "type": "image/png", "size": 256},
        asset=f"{workspace.id}/{uuid4().hex}-{name}",
        size=256,
        workspace=workspace,
        project=project,
        created_by=created_by,
        entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
        is_uploaded=True,
        storage_metadata={"size": 256},
    )
    asset.save(disable_auto_set_user=True)
    return asset


@pytest.fixture
def projects(db, workspace, create_user):
    target = Project.objects.create(
        name="Target Project",
        identifier="TARGET",
        workspace=workspace,
        created_by=create_user,
    )
    other = Project.objects.create(
        name="Other Project",
        identifier="OTHER",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.bulk_create(
        [
            ProjectMember(
                project=target,
                member=create_user,
                workspace=workspace,
                role=20,
            ),
            ProjectMember(
                project=other,
                member=create_user,
                workspace=workspace,
                role=20,
            ),
        ]
    )
    return target, other


@pytest.mark.contract
class TestProjectBulkAssetAssociationScope:
    @pytest.mark.django_db
    def test_uploader_can_associate_fresh_unassigned_asset(
        self, session_client, workspace, create_user, projects
    ):
        target, _ = projects
        asset = create_cover_asset(workspace=workspace, created_by=create_user)

        response = session_client.post(
            bulk_asset_url(workspace.slug, target.id),
            {"asset_ids": [str(asset.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        asset.refresh_from_db()
        target.refresh_from_db()
        assert asset.project_id == target.id
        assert target.cover_image_asset_id == asset.id

    @pytest.mark.django_db
    def test_member_cannot_associate_another_users_asset(
        self, session_client, workspace, create_user, projects
    ):
        target, _ = projects
        other_user = User.objects.create(
            email=f"other-{uuid4().hex[:8]}@plane.so",
            username=f"other_{uuid4().hex[:8]}",
        )
        asset = create_cover_asset(workspace=workspace, created_by=other_user)

        response = session_client.post(
            bulk_asset_url(workspace.slug, target.id),
            {"asset_ids": [str(asset.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        target.refresh_from_db()
        assert asset.project_id is None
        assert target.cover_image_asset_id is None

    @pytest.mark.django_db
    def test_uploader_cannot_move_asset_from_another_project(
        self, session_client, workspace, create_user, projects
    ):
        target, other = projects
        asset = create_cover_asset(
            workspace=workspace,
            created_by=create_user,
            project=other,
        )

        response = session_client.post(
            bulk_asset_url(workspace.slug, target.id),
            {"asset_ids": [str(asset.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        target.refresh_from_db()
        assert asset.project_id == other.id
        assert target.cover_image_asset_id is None
