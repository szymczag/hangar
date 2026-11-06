# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A project's cover and a workspace's logo can only name their own asset.

Both columns are writable foreign keys, and completing the next upload of that
kind soft-deletes whatever the column points at as the "previous" one. Without
these checks, anybody who could edit one project -- every project's creator --
could point its cover at another project's cover, an attachment, or a file in
another workspace, and then delete it by uploading a cover of their own.
"""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import FileAsset, Project, ProjectMember, User, Workspace, WorkspaceMember
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

setup_instance = _google_auth.setup_instance


def _project(workspace, owner, identifier):
    project = Project.objects.create(name=identifier, identifier=identifier, workspace=workspace, created_by=owner)
    ProjectMember.objects.create(project=project, workspace=workspace, member=owner, role=20, is_active=True)
    return project


def _asset(workspace, owner, entity_type, project=None):
    asset = FileAsset(
        attributes={"name": "a.png", "type": "image/png", "size": 24},
        asset=f"{workspace.id}/{uuid4().hex}-a.png",
        size=24,
        workspace=workspace,
        project=project,
        created_by=owner,
        entity_type=entity_type,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )
    asset.save(disable_auto_set_user=True)
    return asset


@pytest.fixture
def own_project(workspace, create_user):
    return _project(workspace, create_user, "OWN")


@pytest.fixture
def other_project(workspace, create_user):
    return _project(workspace, create_user, "OTH")


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectCoverReference:
    def _patch(self, client, workspace, project, value):
        return client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{project.id}/",
            {"cover_image_asset": value},
            format="json",
        )

    def test_another_projects_cover_is_refused(
        self, session_client, workspace, create_user, own_project, other_project
    ):
        foreign = _asset(workspace, create_user, FileAsset.EntityTypeContext.PROJECT_COVER, other_project)

        response = self._patch(session_client, workspace, own_project, str(foreign.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        own_project.refresh_from_db()
        assert own_project.cover_image_asset_id is None

    def test_an_attachment_is_refused(self, session_client, workspace, create_user, own_project):
        attachment = _asset(workspace, create_user, FileAsset.EntityTypeContext.ISSUE_ATTACHMENT, own_project)

        response = self._patch(session_client, workspace, own_project, str(attachment.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_own_cover_and_none_are_accepted(self, session_client, workspace, create_user, own_project):
        cover = _asset(workspace, create_user, FileAsset.EntityTypeContext.PROJECT_COVER, own_project)

        assert self._patch(session_client, workspace, own_project, str(cover.id)).status_code == status.HTTP_200_OK
        own_project.refresh_from_db()
        assert own_project.cover_image_asset_id == cover.id
        assert self._patch(session_client, workspace, own_project, None).status_code == status.HTTP_200_OK

    def test_a_new_project_cannot_start_with_someone_elses_asset(
        self, session_client, workspace, create_user, other_project
    ):
        foreign = _asset(workspace, create_user, FileAsset.EntityTypeContext.PROJECT_COVER, other_project)

        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/projects/",
            {"name": "New", "identifier": "NEW", "cover_image_asset": str(foreign.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Project.objects.filter(identifier="NEW", workspace=workspace).exists()


@pytest.mark.contract
@pytest.mark.django_db
class TestWorkspaceLogoReference:
    def test_another_workspaces_logo_is_refused(self, session_client, workspace, create_user):
        elsewhere = Workspace.objects.create(name="Elsewhere", owner=create_user, slug=f"else-{uuid4().hex[:6]}")
        WorkspaceMember.objects.create(workspace=elsewhere, member=create_user, role=20)
        foreign = _asset(elsewhere, create_user, FileAsset.EntityTypeContext.WORKSPACE_LOGO)

        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/", {"logo_asset": str(foreign.id)}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        workspace.refresh_from_db()
        assert workspace.logo_asset_id is None


@pytest.mark.contract
@pytest.mark.django_db
class TestPreviousAssetDeletionIsScoped:
    def test_completing_a_cover_leaves_a_foreign_previous_asset_alone(
        self, session_client, workspace, create_user, own_project, other_project
    ):
        """A row written before the serializer checked the column must not be deleted either."""
        foreign = _asset(workspace, create_user, FileAsset.EntityTypeContext.PROJECT_COVER, other_project)
        Project.objects.filter(pk=own_project.pk).update(cover_image_asset=foreign)
        new_cover = _asset(workspace, create_user, FileAsset.EntityTypeContext.PROJECT_COVER, own_project)
        FileAsset.objects.filter(pk=new_cover.pk).update(is_uploaded=False)

        def complete(*, asset_id, storage):
            asset = FileAsset.objects.get(pk=asset_id)
            asset.is_uploaded = True
            asset.save(update_fields=["is_uploaded"])
            return asset, True, None

        with mock.patch("plane.app.views.asset.v2.complete_asset_upload", side_effect=complete):
            response = session_client.patch(f"/api/assets/v2/workspaces/{workspace.slug}/{new_cover.id}/")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        foreign.refresh_from_db()
        assert foreign.is_deleted is False
        own_project.refresh_from_db()
        assert own_project.cover_image_asset_id == new_cover.id


@pytest.mark.contract
@pytest.mark.django_db
class TestInstanceAdminWorkspaceLogo:
    """The god-mode workspace create takes the same field and must refuse it too."""

    @pytest.fixture
    def admin_client(self, db, setup_instance):
        admin = User.objects.create(email="admin@ops.example", username=uuid4().hex)
        InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
        client = APIClient()
        authenticate_admin(client, admin)
        return client

    def test_a_new_workspace_cannot_start_with_someone_elses_logo(self, admin_client, workspace, create_user):
        foreign = _asset(workspace, create_user, FileAsset.EntityTypeContext.WORKSPACE_LOGO)

        response = admin_client.post(
            "/api/instances/workspaces/",
            {"name": "Fresh", "slug": "fresh-ws", "logo_asset": str(foreign.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Workspace.objects.filter(slug="fresh-ws").exists()

    def test_a_new_workspace_without_a_logo_is_created(self, admin_client):
        response = admin_client.post(
            "/api/instances/workspaces/", {"name": "Fresh", "slug": "fresh-ws"}, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
