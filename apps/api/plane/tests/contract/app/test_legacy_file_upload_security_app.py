# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from unittest import mock
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from plane.db.models import (
    DeployBoard,
    DraftIssue,
    FileAsset,
    Issue,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    User,
)
from plane.settings.storage import S3Storage
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION


def _png_upload(name="avatar.png"):
    return SimpleUploadedFile(
        name,
        b"\x89PNG\r\n\x1a\nvalidated-raster-test",
        content_type="image/png",
    )


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Secure Upload Project",
        identifier=f"U{uuid4().hex[:4]}",
        workspace=workspace,
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
def issue(db, workspace, project):
    return Issue.objects.create(
        name="Secure upload issue",
        workspace=workspace,
        project=project,
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_legacy_user_upload_rejects_client_owned_security_fields(
    session_client,
):
    response = session_client.post(
        "/api/users/file-assets/",
        {
            "asset": _png_upload(),
            "entity_type": FileAsset.EntityTypeContext.USER_AVATAR,
            "is_uploaded": True,
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "unsupported_legacy_field"


@pytest.mark.contract
@pytest.mark.django_db
@mock.patch(
    "plane.utils.file_asset_upload.magic.from_buffer",
    return_value="image/png",
)
def test_legacy_user_upload_validates_and_marks_server_owned_asset(
    _magic,
    session_client,
    create_user,
):
    response = session_client.post(
        "/api/users/file-assets/",
        {
            "asset": _png_upload(),
            "entity_type": FileAsset.EntityTypeContext.USER_AVATAR,
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    asset = FileAsset.objects.get(id=response.data["id"])
    try:
        assert asset.user_id == create_user.id
        assert asset.workspace_id is None
        assert asset.is_uploaded is True
        assert asset.attributes["type"] == "image/png"
        assert asset.upload_validation_version == UPLOAD_VALIDATION_VERSION
        assert asset.storage_metadata["ValidationVersion"] == UPLOAD_VALIDATION_VERSION
    finally:
        S3Storage().delete_files([asset.asset.name])


@pytest.mark.contract
@pytest.mark.django_db
def test_legacy_user_upload_rejects_unsupported_extension(session_client):
    response = session_client.post(
        "/api/users/file-assets/",
        {
            "asset": SimpleUploadedFile(
                "payload.html",
                b"<script>alert(1)</script>",
                content_type="text/html",
            ),
            "entity_type": FileAsset.EntityTypeContext.USER_AVATAR,
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["code"] == "unsupported_file_extension"


@pytest.mark.contract
@pytest.mark.django_db
def test_legacy_issue_upload_rejects_issue_from_another_project(
    session_client,
    workspace,
    project,
):
    other_project = Project.objects.create(
        name="Other Project",
        identifier=f"O{uuid4().hex[:4]}",
        workspace=workspace,
    )
    other_issue = Issue.objects.create(
        name="Other issue",
        workspace=workspace,
        project=other_project,
    )
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{other_issue.id}/issue-attachments/"

    response = session_client.post(
        url,
        {"asset": _png_upload("attachment.png")},
        format="multipart",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not FileAsset.objects.filter(issue=other_issue).exists()


@pytest.mark.contract
@pytest.mark.django_db
@mock.patch("plane.app.views.issue.attachment.issue_activity.delay")
@mock.patch(
    "plane.utils.file_asset_upload.magic.from_buffer",
    return_value="image/png",
)
def test_legacy_issue_upload_persists_only_scoped_validated_fields(
    _magic,
    _activity,
    session_client,
    workspace,
    project,
    issue,
    create_user,
):
    url = f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/issue-attachments/"

    response = session_client.post(
        url,
        {"asset": _png_upload("attachment.png")},
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    asset = FileAsset.objects.get(id=response.data["id"])
    try:
        assert asset.workspace_id == workspace.id
        assert asset.project_id == project.id
        assert asset.issue_id == issue.id
        assert asset.created_by_id == create_user.id
        assert asset.entity_type == FileAsset.EntityTypeContext.ISSUE_ATTACHMENT
        assert asset.upload_validation_version == UPLOAD_VALIDATION_VERSION
        assert asset.storage_metadata["ValidationVersion"] == UPLOAD_VALIDATION_VERSION
    finally:
        S3Storage().delete_files([asset.asset.name])


@pytest.mark.contract
@pytest.mark.django_db
def test_project_asset_upload_rejects_draft_from_another_project(
    session_client,
    workspace,
    project,
):
    other_project = Project.objects.create(
        name="Other Draft Project",
        identifier=f"D{uuid4().hex[:4]}",
        workspace=workspace,
    )
    other_draft = DraftIssue.objects.create(
        name="Private draft",
        workspace=workspace,
        project=other_project,
    )
    url = f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/"

    response = session_client.post(
        url,
        {
            "name": "draft.png",
            "type": "image/png",
            "size": 32,
            "entity_type": FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
            "entity_identifier": str(other_draft.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not FileAsset.objects.filter(draft_issue=other_draft).exists()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("legacy_multipart", [False, True])
def test_asset_upload_rejects_another_users_private_draft_in_same_project(
    legacy_multipart,
    session_client,
    workspace,
    project,
):
    other_user = User.objects.create(
        email=f"draft-owner-{uuid4().hex[:8]}@plane.so",
        username=f"draft_owner_{uuid4().hex[:8]}",
    )
    ProjectMember.objects.create(
        project=project,
        workspace=workspace,
        member=other_user,
        role=15,
        is_active=True,
    )
    other_draft = DraftIssue.objects.create(
        name="Another user's private draft",
        workspace=workspace,
        project=project,
        created_by=other_user,
    )

    if legacy_multipart:
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/file-assets/",
            {
                "asset": _png_upload("draft.png"),
                "entity_type": FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
                "entity_identifier": str(other_draft.id),
            },
            format="multipart",
        )
    else:
        response = session_client.post(
            f"/api/assets/v2/workspaces/{workspace.slug}/projects/{project.id}/",
            {
                "name": "draft.png",
                "type": "image/png",
                "size": 32,
                "entity_type": FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
                "entity_identifier": str(other_draft.id),
            },
            format="json",
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not FileAsset.objects.filter(draft_issue=other_draft).exists()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("legacy_multipart", [False, True])
def test_workspace_upload_rejects_public_page_without_project_membership(
    legacy_multipart,
    session_client,
    workspace,
):
    foreign_project = Project.objects.create(
        name="Foreign page project",
        identifier=f"F{uuid4().hex[:4]}",
        workspace=workspace,
    )
    page_owner = User.objects.create(
        email=f"page-owner-{uuid4().hex[:8]}@plane.so",
        username=f"page_owner_{uuid4().hex[:8]}",
    )
    foreign_page = Page.objects.create(
        name="Public but project-scoped",
        workspace=workspace,
        owned_by=page_owner,
        access=Page.PUBLIC_ACCESS,
    )
    ProjectPage.objects.create(
        page=foreign_page,
        project=foreign_project,
        workspace=workspace,
    )

    if legacy_multipart:
        response = session_client.post(
            f"/api/workspaces/{workspace.slug}/file-assets/",
            {
                "asset": _png_upload("page.png"),
                "entity_type": FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
                "entity_identifier": str(foreign_page.id),
            },
            format="multipart",
        )
    else:
        response = session_client.post(
            f"/api/assets/v2/workspaces/{workspace.slug}/",
            {
                "name": "page.png",
                "type": "image/png",
                "size": 32,
                "entity_type": FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
                "entity_identifier": str(foreign_page.id),
            },
            format="json",
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not FileAsset.objects.filter(page=foreign_page).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_space_asset_completion_rechecks_active_project_membership(
    session_client,
    workspace,
    project,
    create_user,
):
    board = DeployBoard.objects.create(
        workspace=workspace,
        project=project,
        entity_name="project",
        entity_identifier=project.id,
    )
    asset = FileAsset(
        attributes={"name": "pending.png", "type": "image/png", "size": 32},
        asset=f"{workspace.id}/pending/pending.png",
        size=32,
        workspace=workspace,
        project=project,
        entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
    )
    asset.save(created_by_id=create_user.id)
    ProjectMember.objects.filter(
        project=project,
        member=create_user,
    ).update(is_active=False)

    with mock.patch(
        "plane.space.views.asset.complete_asset_upload",
    ) as complete_upload:
        response = session_client.patch(
            f"/api/public/assets/v2/anchor/{board.anchor}/{asset.id}/",
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        complete_upload.assert_not_called()


@pytest.mark.contract
@pytest.mark.django_db
def test_space_legacy_asset_is_never_rendered_inline(
    session_client,
    workspace,
    project,
    create_user,
):
    board = DeployBoard.objects.create(
        workspace=workspace,
        project=project,
        entity_name="project",
        entity_identifier=project.id,
    )
    asset = FileAsset(
        attributes={"name": "legacy.png", "type": "image/png", "size": 32},
        asset=f"{workspace.id}/legacy.png",
        size=32,
        workspace=workspace,
        project=project,
        entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        is_uploaded=True,
    )
    asset.save(created_by_id=create_user.id)

    with mock.patch("plane.space.views.asset.S3Storage") as storage_class:
        storage = storage_class.return_value
        storage.generate_presigned_url.return_value = "https://signed.example/legacy"
        response = session_client.get(f"/api/public/assets/v2/anchor/{board.anchor}/{asset.id}/")

    assert response.status_code == status.HTTP_302_FOUND
    storage.generate_presigned_url.assert_called_once_with(
        object_name=asset.asset.name,
        disposition="attachment",
        content_type="application/octet-stream",
    )
