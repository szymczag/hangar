# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import FileAsset, Issue, Project, ProjectMember, User, WorkspaceMember
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION


@pytest.fixture
def attachment_context(db, workspace, create_user):
    project = Project.objects.create(
        name="API attachment scope",
        identifier=f"A{uuid4().hex[:4]}",
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
    member = User.objects.create(
        email=f"api-member-{uuid4().hex[:8]}@plane.so",
        username=f"api_member_{uuid4().hex[:8]}",
    )
    WorkspaceMember.objects.create(
        workspace=workspace,
        member=member,
        role=15,
        is_active=True,
    )
    membership = ProjectMember.objects.create(
        project=project,
        workspace=workspace,
        member=member,
        role=15,
        is_active=True,
    )
    issue = Issue.objects.create(
        name="Attachment scope",
        workspace=workspace,
        project=project,
        created_by=member,
    )
    client = APIClient()
    client.force_authenticate(user=member)
    return project, issue, member, membership, client


def create_attachment(*, workspace, project, issue, creator, uploaded=True):
    asset = FileAsset(
        attributes={"name": "evidence.pdf", "type": "application/pdf", "size": 12},
        asset=f"{workspace.id}/{uuid4().hex}-evidence.pdf",
        size=12,
        workspace=workspace,
        project=project,
        issue=issue,
        created_by=creator,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        is_uploaded=uploaded,
        upload_validation_version=(UPLOAD_VALIDATION_VERSION if uploaded else 0),
        storage_metadata={"private": "must-not-be-serialized"},
    )
    asset.save(disable_auto_set_user=True)
    return asset


def list_url(workspace, project, issue):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue.id}/attachments/"


@pytest.mark.contract
class TestIssueAttachmentAPISecurity:
    @pytest.mark.django_db
    def test_active_member_list_omits_storage_details(
        self,
        workspace,
        create_user,
        attachment_context,
    ):
        project, issue, _member, _membership, client = attachment_context
        create_attachment(
            workspace=workspace,
            project=project,
            issue=issue,
            creator=create_user,
        )

        response = client.get(list_url(workspace, project, issue))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert "asset" not in response.data[0]
        assert "storage_metadata" not in response.data[0]

    @pytest.mark.django_db
    def test_revoked_issue_creator_cannot_list_or_complete(
        self,
        workspace,
        attachment_context,
    ):
        project, issue, member, membership, client = attachment_context
        attachment = create_attachment(
            workspace=workspace,
            project=project,
            issue=issue,
            creator=member,
            uploaded=False,
        )
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        list_response = client.get(list_url(workspace, project, issue))
        patch_response = client.patch(
            f"{list_url(workspace, project, issue)}{attachment.id}/",
            {"is_uploaded": True},
            format="json",
        )

        assert list_response.status_code == status.HTTP_403_FORBIDDEN
        assert patch_response.status_code == status.HTTP_403_FORBIDDEN
        attachment.refresh_from_db()
        assert attachment.is_uploaded is False

    @pytest.mark.django_db
    def test_non_admin_member_cannot_delete_another_users_attachment(
        self,
        workspace,
        create_user,
        attachment_context,
    ):
        project, issue, _member, _membership, client = attachment_context
        attachment = create_attachment(
            workspace=workspace,
            project=project,
            issue=issue,
            creator=create_user,
        )

        response = client.delete(f"{list_url(workspace, project, issue)}{attachment.id}/")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        attachment.refresh_from_db()
        assert attachment.is_deleted is False
