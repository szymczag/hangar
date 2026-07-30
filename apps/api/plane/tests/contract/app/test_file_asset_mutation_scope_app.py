# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    DraftIssue,
    FileAsset,
    Issue,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    User,
    WorkspaceMember,
)
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Mutation scope",
        identifier=f"M{uuid4().hex[:4]}",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        workspace=workspace,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


@pytest.fixture
def member(db, workspace, project):
    user = User.objects.create(
        email=f"member-{uuid4().hex[:8]}@plane.so",
        username=f"member_{uuid4().hex[:8]}",
    )
    WorkspaceMember.objects.create(
        workspace=workspace,
        member=user,
        role=15,
        is_active=True,
    )
    ProjectMember.objects.create(
        project=project,
        workspace=workspace,
        member=user,
        role=15,
        is_active=True,
    )
    return user


@pytest.fixture
def member_client(member):
    client = APIClient()
    client.force_authenticate(user=member)
    return client


def create_asset(*, workspace, creator, entity_type, project=None, issue=None, page=None):
    asset = FileAsset(
        attributes={"name": "asset.png", "type": "image/png", "size": 24},
        asset=f"{workspace.id}/{uuid4().hex}-asset.png",
        size=24,
        workspace=workspace,
        project=project,
        issue=issue,
        page=page,
        created_by=creator,
        entity_type=entity_type,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )
    asset.save(disable_auto_set_user=True)
    return asset


@pytest.mark.contract
class TestFileAssetMutationScope:
    @pytest.mark.django_db
    def test_project_member_cannot_delete_another_users_asset(
        self,
        member_client,
        workspace,
        project,
        create_user,
    ):
        asset = create_asset(
            workspace=workspace,
            project=project,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        )

        response = member_client.delete(f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/{asset.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.is_deleted is False

    @pytest.mark.django_db
    def test_workspace_member_cannot_delete_workspace_level_asset(
        self,
        member_client,
        workspace,
        create_user,
    ):
        asset = create_asset(
            workspace=workspace,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.WORKSPACE_LOGO,
        )

        response = member_client.delete(f"/api/assets/v2/workspaces/{workspace.slug}/{asset.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.is_deleted is False

    @pytest.mark.django_db
    def test_workspace_member_cannot_restore_another_users_asset(
        self,
        member_client,
        workspace,
        create_user,
    ):
        asset = create_asset(
            workspace=workspace,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        )
        asset.is_deleted = True
        asset.save(update_fields=["is_deleted"])

        response = member_client.post(f"/api/assets/v2/workspaces/{workspace.slug}/restore/{asset.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.is_deleted is True

    @pytest.mark.django_db
    @pytest.mark.parametrize("legacy", [True, False])
    def test_revoked_project_member_cannot_delete_own_attachment(
        self,
        legacy,
        member_client,
        member,
        workspace,
        project,
    ):
        issue = Issue.objects.create(
            name="Scoped issue",
            workspace=workspace,
            project=project,
        )
        asset = create_asset(
            workspace=workspace,
            project=project,
            issue=issue,
            creator=member,
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        )
        ProjectMember.objects.filter(project=project, member=member).update(is_active=False)
        if legacy:
            url = (
                f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/"
                f"{issue.id}/issue-attachments/{asset.id}/"
            )
        else:
            url = (
                f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/issues/"
                f"{issue.id}/attachments/{asset.id}/"
            )

        response = member_client.delete(url)

        assert response.status_code in {
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }
        assert FileAsset.objects.filter(id=asset.id).exists()

    @pytest.mark.django_db
    def test_duplicate_rejects_unvalidated_legacy_source(
        self,
        session_client,
        workspace,
        project,
        create_user,
    ):
        asset = create_asset(
            workspace=workspace,
            project=project,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
        )
        asset.upload_validation_version = 0
        asset.save(update_fields=["upload_validation_version"])

        response = session_client.post(
            f"/api/assets/v2/workspaces/{workspace.slug}/duplicate-assets/{asset.id}/",
            {
                "project_id": str(project.id),
                "entity_id": str(project.id),
                "entity_type": FileAsset.EntityTypeContext.PROJECT_COVER,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.django_db
    def test_duplicate_republishes_validated_source_with_trusted_marker(
        self,
        session_client,
        workspace,
        project,
        create_user,
    ):
        asset = create_asset(
            workspace=workspace,
            project=project,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
        )
        asset.storage_metadata = {"DetectedContentType": "image/png"}
        asset.save(update_fields=["storage_metadata"])

        with mock.patch("plane.app.views.asset.v2.S3Storage") as storage_class:
            storage = storage_class.return_value
            storage.get_object_metadata.side_effect = [
                {
                    "ContentType": "image/png",
                    "ContentLength": 24,
                    "ETag": '"source-etag"',
                },
                {
                    "ContentType": "image/png",
                    "ContentLength": 24,
                    "ETag": '"copy-etag"',
                },
            ]
            storage.copy_object.return_value = {"CopyObjectResult": {}}
            response = session_client.post(
                f"/api/assets/v2/workspaces/{workspace.slug}/duplicate-assets/{asset.id}/",
                {
                    "project_id": str(project.id),
                    "entity_id": str(project.id),
                    "entity_type": FileAsset.EntityTypeContext.PROJECT_COVER,
                },
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        duplicate = FileAsset.objects.get(id=response.data["asset_id"])
        assert duplicate.project_id == project.id
        assert duplicate.is_uploaded is True
        assert duplicate.upload_validation_version == UPLOAD_VALIDATION_VERSION
        assert duplicate.storage_metadata["ValidationVersion"] == UPLOAD_VALIDATION_VERSION
        storage.copy_object.assert_called_once_with(
            asset.asset.name,
            duplicate.asset.name,
            source_etag='"source-etag"',
            content_type="image/png",
        )

    @pytest.mark.django_db
    def test_legacy_member_cannot_delete_or_restore_another_users_asset(
        self,
        member_client,
        workspace,
        project,
        create_user,
    ):
        asset = create_asset(
            workspace=workspace,
            project=project,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        )
        asset_key = asset.asset.name.split("/", 1)[1]
        url = f"/api/workspaces/file-assets/{workspace.id}/{asset_key}/"

        delete_response = member_client.delete(url)
        restore_response = member_client.post(f"{url}restore/")

        assert delete_response.status_code == status.HTTP_404_NOT_FOUND
        assert restore_response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.is_deleted is False

    @pytest.mark.django_db
    def test_project_member_cannot_read_private_page_asset(
        self,
        member_client,
        workspace,
        project,
        create_user,
    ):
        page = Page.objects.create(
            name="Private page",
            workspace=workspace,
            owned_by=create_user,
            access=Page.PRIVATE_ACCESS,
        )
        asset = create_asset(
            workspace=workspace,
            project=project,
            page=page,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        )

        with mock.patch("plane.app.views.asset.v2.S3Storage") as storage_class:
            response = member_client.get(
                f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/{asset.id}/"
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        storage_class.return_value.generate_presigned_url.assert_not_called()

    @pytest.mark.django_db
    def test_duplicate_rejects_unreadable_private_page_source(
        self,
        member_client,
        member,
        workspace,
        project,
        create_user,
    ):
        page = Page.objects.create(
            name="Private source",
            workspace=workspace,
            owned_by=create_user,
            access=Page.PRIVATE_ACCESS,
        )
        source = create_asset(
            workspace=workspace,
            project=project,
            page=page,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        )

        with mock.patch("plane.app.views.asset.v2.S3Storage") as storage_class:
            response = member_client.post(
                f"/api/assets/v2/workspaces/{workspace.slug}/duplicate-assets/{source.id}/",
                {
                    "project_id": str(project.id),
                    "entity_id": str(project.id),
                    "entity_type": FileAsset.EntityTypeContext.PROJECT_COVER,
                },
                format="json",
            )

        assert member.id != create_user.id
        assert response.status_code == status.HTTP_404_NOT_FOUND
        storage_class.return_value.copy_object.assert_not_called()

    @pytest.mark.django_db
    def test_duplicate_rejects_another_users_private_draft_destination(
        self,
        member_client,
        member,
        workspace,
        project,
        create_user,
    ):
        draft = DraftIssue.objects.create(
            name="Private destination",
            workspace=workspace,
            project=project,
            created_by=create_user,
        )
        source = create_asset(
            workspace=workspace,
            project=project,
            creator=member,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
        )

        with mock.patch("plane.app.views.asset.v2.S3Storage") as storage_class:
            response = member_client.post(
                f"/api/assets/v2/workspaces/{workspace.slug}/duplicate-assets/{source.id}/",
                {
                    "project_id": str(project.id),
                    "entity_id": str(draft.id),
                    "entity_type": FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
                },
                format="json",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        storage_class.return_value.copy_object.assert_not_called()

    @pytest.mark.django_db
    def test_duplicate_rejects_public_page_without_destination_project_membership(
        self,
        member_client,
        member,
        workspace,
        project,
        create_user,
    ):
        foreign_project = Project.objects.create(
            name="Foreign page project",
            identifier=f"F{uuid4().hex[:4]}",
            workspace=workspace,
        )
        foreign_page = Page.objects.create(
            name="Foreign public destination",
            workspace=workspace,
            owned_by=create_user,
            access=Page.PUBLIC_ACCESS,
        )
        ProjectPage.objects.create(
            page=foreign_page,
            project=foreign_project,
            workspace=workspace,
        )
        source = create_asset(
            workspace=workspace,
            project=project,
            creator=member,
            entity_type=FileAsset.EntityTypeContext.PROJECT_COVER,
        )

        with mock.patch("plane.app.views.asset.v2.S3Storage") as storage_class:
            response = member_client.post(
                f"/api/assets/v2/workspaces/{workspace.slug}/duplicate-assets/{source.id}/",
                {
                    "entity_id": str(foreign_page.id),
                    "entity_type": FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
                },
                format="json",
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        storage_class.return_value.copy_object.assert_not_called()

    @pytest.mark.django_db
    def test_project_member_cannot_convert_another_users_draft_or_reassign_assets(
        self,
        member_client,
        workspace,
        project,
        create_user,
    ):
        draft = DraftIssue.objects.create(
            name="Private draft",
            workspace=workspace,
            project=project,
            created_by=create_user,
        )
        asset = create_asset(
            workspace=workspace,
            project=project,
            creator=create_user,
            entity_type=FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
        )
        asset.draft_issue = draft
        asset.save(update_fields=["draft_issue"])

        response = member_client.post(
            f"/api/workspaces/{workspace.slug}/draft-to-issue/{draft.id}/",
            {
                "name": "Stolen issue",
                "project_id": str(project.id),
            },
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert DraftIssue.objects.filter(id=draft.id).exists()
        asset.refresh_from_db()
        assert asset.draft_issue_id == draft.id
        assert asset.issue_id is None
