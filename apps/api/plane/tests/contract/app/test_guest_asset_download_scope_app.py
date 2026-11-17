# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Imported pytest fixtures are requested by parameter name, which F811 misreads as redefinition.
# ruff: noqa: F811

"""A restricted guest (``guest_view_all_features=False``) must not read, by asset id,
the files of issues they did not create: attachments, description images and
comment images (GHSA-wq96-4xjj-j4qg). ``can_read_file_asset`` applies the rule for
every asset read route, the check route, duplication, the legacy file route, the
external API generic asset route and the description-image copy task;
``FileAsset.is_project_accessible_to`` applies it as well. Own issues, members,
admins and unrestricted guests are unaffected.

Reuses the fixtures of the sibling sub-resource test module.
"""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.bgtasks.copy_s3_object import copy_assets
from plane.db.models import APIToken, FileAsset, ProjectMember, User, WorkspaceMember
from plane.tests.contract.app.test_guest_issue_subresource_scope_app import (  # noqa: F401
    _make_comment,
    foreign_issue,
    guest,
    guest_client,
    own_issue,
    project,
)
from plane.utils.file_asset_permissions import can_read_file_asset
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

S3_STORAGE_PATH = "plane.app.views.asset.v2.S3Storage"

READ_URLS = [
    "/api/assets/v2/workspaces/{slug}/download/{asset_id}/",
    "/api/assets/v2/workspaces/{slug}/projects/{project_id}/download/{asset_id}/",
    "/api/assets/v2/workspaces/{slug}/{asset_id}/",
    "/api/assets/v2/workspaces/{slug}/projects/{project_id}/{asset_id}/",
]
# Hangar answers an unreadable asset with 404 wherever ``can_read_file_asset`` runs
# first, so the response does not confirm the asset exists. The workspace asset
# route runs ``is_project_accessible_to`` first, which answers 403.
HIDDEN = [
    status.HTTP_404_NOT_FOUND,
    status.HTTP_404_NOT_FOUND,
    status.HTTP_403_FORBIDDEN,
    status.HTTP_404_NOT_FOUND,
]
SERVED = [status.HTTP_302_FOUND] * 4
CHECK_URL = "/api/assets/v2/workspaces/{slug}/check/{asset_id}/"
DUPLICATE_URL = "/api/assets/v2/workspaces/{slug}/duplicate-assets/{asset_id}/"
V1_ASSET_URL = "/api/v1/workspaces/{slug}/assets/{asset_id}/"
LEGACY_FILE_URL = "/api/workspaces/file-assets/{workspace_id}/{asset_key}/"


def _url(tpl, workspace, project, asset):
    return tpl.format(slug=workspace.slug, project_id=project.id, asset_id=asset.id)


def _attachment(issue):
    return FileAsset.objects.get(issue=issue, entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT)


def _get_all(client, workspace, project, asset):
    """Status codes of every read route for ``asset``; storage is mocked."""
    with mock.patch(S3_STORAGE_PATH) as storage:
        storage.return_value.generate_presigned_url.return_value = "https://example.com/s"
        return [client.get(_url(tpl, workspace, project, asset)).status_code for tpl in READ_URLS]


def _description_asset(workspace, project, issue):
    return FileAsset.objects.create(
        attributes={"name": "diagram.png", "type": "image/png", "size": 100},
        asset=f"{workspace.id}/{uuid4().hex}-diagram.png",
        size=100,
        workspace=workspace,
        project=project,
        issue_id=issue.id,
        entity_type=FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )


def _copyable(asset):
    """Mark ``asset`` server-validated so only the read rule can stop a copy of it."""
    asset.upload_validation_version = UPLOAD_VALIDATION_VERSION
    asset.save(update_fields=["upload_validation_version"])
    return asset


def _duplicate(client, workspace, project, asset, target_issue):
    with mock.patch(S3_STORAGE_PATH) as storage:
        storage.return_value.get_object_metadata.side_effect = [
            {"ContentType": "application/pdf", "ContentLength": 100, "ETag": '"source"'},
            {"ContentType": "application/pdf", "ContentLength": 100, "ETag": '"copy"'},
        ]
        storage.return_value.copy_object.return_value = {"CopyObjectResult": {}}
        response = client.post(
            _url(DUPLICATE_URL, workspace, project, asset),
            {
                "entity_type": FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                "entity_id": str(target_issue.id),
                "project_id": str(project.id),
            },
            format="json",
        )
    return response, storage.return_value


@pytest.fixture
def foreign_description_asset(workspace, project, foreign_issue):
    return _description_asset(workspace, project, foreign_issue)


@pytest.fixture
def foreign_comment_asset(workspace, project, foreign_issue, create_user):
    # Comment images carry the comment, not the issue (ProjectBulkAssetEndpoint).
    comment = _make_comment(foreign_issue, project, workspace, create_user)
    return FileAsset.objects.create(
        attributes={"name": "screenshot.png", "type": "image/png", "size": 100},
        asset=f"{workspace.id}/{uuid4().hex}-screenshot.png",
        workspace=workspace,
        project=project,
        comment_id=comment.id,
        entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
        is_uploaded=True,
    )


@pytest.fixture
def own_comment_asset(workspace, project, own_issue, guest):
    comment = _make_comment(own_issue, project, workspace, guest)
    return FileAsset.objects.create(
        attributes={"name": "mine.png", "type": "image/png", "size": 100},
        asset=f"{workspace.id}/{uuid4().hex}-mine.png",
        workspace=workspace,
        project=project,
        comment_id=comment.id,
        entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
        is_uploaded=True,
    )


@pytest.fixture
def foreign_assets(foreign_issue, foreign_description_asset, foreign_comment_asset):
    return [_attachment(foreign_issue), foreign_description_asset, foreign_comment_asset]


@pytest.fixture
def member(db, workspace, project):
    """An active project MEMBER (role 15)."""
    user = User.objects.create(
        email=f"member-{uuid4().hex[:8]}@plane.so",
        username=f"member_{uuid4().hex[:8]}",
        first_name="Member",
    )
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=15)
    return user


@pytest.fixture
def member_client(member):
    client = APIClient()
    client.force_authenticate(user=member)
    return client


@pytest.fixture
def guest_api_client(guest):
    token = APIToken.objects.create(user=guest, label="Guest token", token=f"guest-{uuid4().hex}")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    return client


@pytest.mark.contract
@pytest.mark.django_db
class TestGuestHiddenIssueAssets:
    def test_guest_blocked_from_foreign_issue_assets(self, guest_client, workspace, project, foreign_assets):
        for asset in foreign_assets:
            assert _get_all(guest_client, workspace, project, asset) == HIDDEN, asset.entity_type

    def test_guest_check_and_duplicate_blocked(self, guest_client, workspace, project, foreign_issue, own_issue):
        asset = _copyable(_attachment(foreign_issue))
        assert guest_client.get(_url(CHECK_URL, workspace, project, asset)).data == {"exists": False}

        # The target is the guest's own issue, a valid destination, so the source's
        # read rule is the only thing standing between the guest and a copy.
        before = FileAsset.objects.count()
        response, storage = _duplicate(guest_client, workspace, project, asset, own_issue)
        # Hangar answers missing and unreadable sources alike (copyable_asset).
        assert response.status_code == status.HTTP_404_NOT_FOUND
        storage.copy_object.assert_not_called()
        assert FileAsset.objects.count() == before

    def test_guest_check_blocked_for_every_asset_kind(self, guest_client, workspace, project, foreign_assets):
        for asset in foreign_assets:
            response = guest_client.get(_url(CHECK_URL, workspace, project, asset))
            assert response.data == {"exists": False}, asset.entity_type

    def test_guest_can_duplicate_own_issue_attachment(self, guest_client, workspace, project, own_issue):
        asset = _copyable(_attachment(own_issue))
        response, storage = _duplicate(guest_client, workspace, project, asset, own_issue)
        assert response.status_code == status.HTTP_200_OK, response.data
        storage.copy_object.assert_called_once()

    def test_guest_blocked_on_external_api_asset(self, guest_api_client, workspace, foreign_assets):
        with mock.patch("plane.api.views.asset.S3Storage") as storage:
            storage.return_value.generate_presigned_url.return_value = "https://example.com/s"
            for asset in foreign_assets:
                response = guest_api_client.get(V1_ASSET_URL.format(slug=workspace.slug, asset_id=asset.id))
                assert response.status_code == status.HTTP_404_NOT_FOUND, asset.entity_type

    def test_guest_allowed_external_api_own_asset(self, guest_api_client, workspace, own_issue):
        with mock.patch("plane.api.views.asset.S3Storage") as storage:
            storage.return_value.generate_presigned_url.return_value = "https://example.com/s"
            response = guest_api_client.get(
                V1_ASSET_URL.format(slug=workspace.slug, asset_id=_attachment(own_issue).id)
            )
        assert response.status_code == status.HTTP_200_OK, response.data

    def test_guest_blocked_on_legacy_file_route(self, guest_client, workspace, foreign_assets, own_issue):
        def legacy(asset):
            asset_key = asset.asset.name.split("/", 1)[1]
            return guest_client.get(LEGACY_FILE_URL.format(workspace_id=workspace.id, asset_key=asset_key)).data

        for asset in foreign_assets:
            assert legacy(asset)["status"] is False, asset.entity_type
        own = legacy(_attachment(own_issue))
        assert own["status"] is True
        assert str(own["data"][0]["id"]) == str(_attachment(own_issue).id)

    def test_copy_task_skips_foreign_description_images(self, guest, workspace, project, foreign_issue, own_issue):
        foreign_image = _description_asset(workspace, project, foreign_issue)
        own_image = _description_asset(workspace, project, own_issue)
        with mock.patch("plane.bgtasks.copy_s3_object.S3Storage") as storage:
            storage.return_value.get_object_metadata.return_value = {
                "ContentType": "image/png",
                "ContentLength": 100,
                "ETag": '"etag"',
            }
            storage.return_value.copy_object.return_value = {"CopyObjectResult": {}}
            copied = copy_assets(
                entity=own_issue,
                entity_identifier=own_issue.id,
                project_id=project.id,
                asset_ids=[foreign_image.id, own_image.id],
                user_id=guest.id,
            )
        assert [entry["old_asset_id"] for entry in copied] == [str(own_image.id)]
        storage.return_value.copy_object.assert_called_once()

    def test_guest_allowed_own_issue_assets(self, guest_client, workspace, project, own_issue, own_comment_asset):
        own_description = _description_asset(workspace, project, own_issue)
        for asset in (_attachment(own_issue), own_description, own_comment_asset):
            assert _get_all(guest_client, workspace, project, asset) == SERVED, asset.entity_type
            assert guest_client.get(_url(CHECK_URL, workspace, project, asset)).data == {"exists": True}

    def test_member_unaffected(self, member_client, workspace, project, foreign_assets):
        for asset in foreign_assets:
            assert _get_all(member_client, workspace, project, asset) == SERVED, asset.entity_type

    def test_admin_unaffected(self, session_client, workspace, project, foreign_assets):
        for asset in foreign_assets:
            assert _get_all(session_client, workspace, project, asset) == SERVED, asset.entity_type

    def test_unrestricted_guest_unaffected(self, guest_client, workspace, project, foreign_assets):
        project.guest_view_all_features = True
        project.save(update_fields=["guest_view_all_features"])
        for asset in foreign_assets:
            assert _get_all(guest_client, workspace, project, asset) == SERVED, asset.entity_type
            assert guest_client.get(_url(CHECK_URL, workspace, project, asset)).data == {"exists": True}

    def test_read_rule_matrix(self, guest, member, create_user, project, foreign_assets, own_issue):
        own = _attachment(own_issue)
        for asset in foreign_assets:
            assert can_read_file_asset(user_id=guest.id, asset=asset) is False, asset.entity_type
            assert asset.is_project_accessible_to(guest) is False, asset.entity_type
            assert can_read_file_asset(user_id=member.id, asset=asset) is True, asset.entity_type
            assert can_read_file_asset(user_id=create_user.id, asset=asset) is True, asset.entity_type
        assert can_read_file_asset(user_id=guest.id, asset=own) is True
        assert own.is_project_accessible_to(guest) is True
