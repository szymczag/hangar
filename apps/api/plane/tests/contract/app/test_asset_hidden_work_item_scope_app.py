# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Work item attachments and description images follow the work item's visibility.

A restricted guest (a GUEST of a project with ``guest_view_all_features`` off)
only reaches the work items they created. Every path that anchors an asset to a
work item applies that rule: the dedicated attachment endpoint, the v2 upload,
duplication and bulk association, and the legacy multipart upload, which also
binds a comment image only to a comment the caller may edit. A hidden work item
gets the same 404 as a missing one. Deleting, restoring and completing an asset
of a hidden work item are refused the same way.
"""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from plane.db.models import FileAsset, Issue, IssueComment, Project, ProjectMember, User, WorkspaceMember
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

S3_STORAGE_PATH = "plane.app.views.asset.v2.S3Storage"
UPLOAD_URL = "/api/assets/v2/workspaces/{slug}/projects/{project_id}/"
BULK_URL = "/api/assets/v2/workspaces/{slug}/projects/{project_id}/{entity_id}/bulk/"
DUPLICATE_URL = "/api/assets/v2/workspaces/{slug}/duplicate-assets/{asset_id}/"
LEGACY_UPLOAD_URL = "/api/workspaces/{slug}/file-assets/"
ASSET_URL = "/api/assets/v2/workspaces/{slug}/projects/{project_id}/{pk}/"
RESTORE_URL = "/api/assets/v2/workspaces/{slug}/restore/{asset_id}/"
LEGACY_ASSET_URL = "/api/workspaces/file-assets/{asset_key}/"
LEGACY_RESTORE_URL = "/api/workspaces/file-assets/{asset_key}/restore/"
PNG = b"\x89PNG\r\n\x1a\nlegacy-work-item-upload"

WORK_ITEM_ENTITY_TYPES = [
    FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
    FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
]


def _user(role, workspace, project):
    user = User.objects.create(email=f"u-{uuid4().hex[:8]}@plane.so", username=uuid4().hex)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    ProjectMember.objects.create(workspace=workspace, project=project, member=user, role=role, is_active=True)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _issue(project, author, name="Work item"):
    issue = Issue(name=name, project=project, workspace=project.workspace)
    issue.save(created_by_id=author.id)
    return issue


def _asset(project, owner, entity_type, issue):
    asset = FileAsset(
        attributes={"name": "image.png", "type": "image/png", "size": 10},
        asset=f"{project.workspace_id}/{uuid4().hex}-image.png",
        size=10,
        workspace=project.workspace,
        project_id=project.id,
        entity_type=entity_type,
        issue=issue,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )
    asset.save(created_by_id=owner.id)
    return asset


@pytest.fixture
def setup(db, workspace, create_user):
    project = Project.objects.create(name="Alpha", identifier="ALP", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
    guest = _user(5, workspace, project)
    return {
        "workspace": workspace,
        "project": project,
        "member": _user(15, workspace, project),
        "admin": _user(20, workspace, project),
        "guest": guest,
        # Written by someone else, so hidden from the restricted guest.
        "hidden_issue": _issue(project, create_user, "Hidden"),
        "guest_issue": _issue(project, guest, "Guest's own"),
    }


def _upload(user, setup, entity_type, issue):
    with mock.patch(S3_STORAGE_PATH) as storage:
        storage.return_value.generate_presigned_post.return_value = {"url": "https://s3.test/", "fields": {}}
        return _client(user).post(
            UPLOAD_URL.format(slug=setup["workspace"].slug, project_id=setup["project"].id),
            {
                "name": "file.png",
                "type": "image/png",
                "size": 2048,
                "entity_type": entity_type,
                "entity_identifier": str(issue.id),
            },
            format="json",
        )


def _duplicate(user, setup, source, entity_type, issue):
    with (
        mock.patch(S3_STORAGE_PATH),
        mock.patch("plane.app.views.asset.v2.duplicate_file_asset", return_value=mock.Mock(id=uuid4())) as copy,
    ):
        response = _client(user).post(
            DUPLICATE_URL.format(slug=setup["workspace"].slug, asset_id=source.id),
            {"entity_type": entity_type, "entity_id": str(issue.id), "project_id": str(setup["project"].id)},
            format="json",
        )
    return response, copy


def _bind(user, setup, asset, issue):
    return _client(user).post(
        BULK_URL.format(slug=setup["workspace"].slug, project_id=setup["project"].id, entity_id=issue.id),
        {"asset_ids": [str(asset.id)]},
        format="json",
    )


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("entity_type", WORK_ITEM_ENTITY_TYPES)
class TestWorkItemAssetVisibility:
    def test_a_restricted_guest_cannot_upload_to_a_hidden_work_item(self, setup, entity_type):
        response = _upload(setup["guest"], setup, entity_type, setup["hidden_issue"])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert not FileAsset.all_objects.filter(issue=setup["hidden_issue"]).exists()

    def test_the_refusal_matches_a_missing_work_item(self, setup, entity_type):
        hidden = _upload(setup["guest"], setup, entity_type, setup["hidden_issue"])
        missing = _upload(setup["guest"], setup, entity_type, mock.Mock(id=uuid4()))

        assert hidden.status_code == missing.status_code == status.HTTP_404_NOT_FOUND
        assert hidden.data == missing.data

    def test_a_restricted_guest_still_uploads_to_their_own_work_item(self, setup, entity_type):
        response = _upload(setup["guest"], setup, entity_type, setup["guest_issue"])

        assert response.status_code == status.HTTP_200_OK, response.data
        assert FileAsset.objects.get(id=response.data["asset_id"]).issue_id == setup["guest_issue"].id

    def test_a_member_still_uploads_to_the_work_item(self, setup, entity_type):
        response = _upload(setup["member"], setup, entity_type, setup["hidden_issue"])

        assert response.status_code == status.HTTP_200_OK, response.data
        assert FileAsset.objects.get(id=response.data["asset_id"]).issue_id == setup["hidden_issue"].id

    def test_a_malformed_identifier_is_still_a_400(self, setup, entity_type):
        response = _upload(setup["guest"], setup, entity_type, mock.Mock(id="not-a-uuid"))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_restricted_guest_cannot_duplicate_onto_a_hidden_work_item(self, setup, entity_type):
        source = _asset(setup["project"], setup["guest"], entity_type, setup["guest_issue"])

        response, copy = _duplicate(setup["guest"], setup, source, entity_type, setup["hidden_issue"])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        copy.assert_not_called()

    def test_a_member_still_duplicates_onto_the_work_item(self, setup, entity_type):
        source = _asset(setup["project"], setup["member"], entity_type, setup["guest_issue"])

        response, copy = _duplicate(setup["member"], setup, source, entity_type, setup["hidden_issue"])

        assert response.status_code == status.HTTP_200_OK, response.data
        assert copy.call_args.kwargs["entity_fields"] == {"issue_id": setup["hidden_issue"].id}

    def test_a_restricted_guest_cannot_rebind_onto_a_hidden_work_item(self, setup, entity_type):
        asset = _asset(setup["project"], setup["guest"], entity_type, setup["guest_issue"])

        response = _bind(setup["guest"], setup, asset, setup["hidden_issue"])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.issue_id == setup["guest_issue"].id

    def test_a_restricted_guest_still_binds_to_their_own_work_item(self, setup, entity_type):
        asset = _asset(setup["project"], setup["guest"], entity_type, None)

        response = _bind(setup["guest"], setup, asset, setup["guest_issue"])

        assert response.status_code == status.HTTP_204_NO_CONTENT
        asset.refresh_from_db()
        assert asset.issue_id == setup["guest_issue"].id

    def test_a_member_still_binds_to_the_work_item(self, setup, entity_type):
        asset = _asset(setup["project"], setup["member"], entity_type, setup["guest_issue"])

        response = _bind(setup["member"], setup, asset, setup["hidden_issue"])

        assert response.status_code == status.HTTP_204_NO_CONTENT
        asset.refresh_from_db()
        assert asset.issue_id == setup["hidden_issue"].id


def _legacy_upload(user, setup, entity_type, entity_id):
    with (
        mock.patch("plane.utils.file_asset_upload.magic.from_buffer", return_value="image/png"),
        mock.patch("plane.app.views.asset.base.S3Storage") as storage,
    ):
        storage.return_value.upload_file.return_value = True
        storage.return_value.get_object_metadata.return_value = {"ContentLength": len(PNG), "ContentType": "image/png"}
        return _client(user).post(
            LEGACY_UPLOAD_URL.format(slug=setup["workspace"].slug),
            {
                "asset": SimpleUploadedFile("file.png", PNG, content_type="image/png"),
                "entity_type": entity_type,
                "entity_identifier": str(entity_id),
            },
            format="multipart",
        )


def _comment(issue, author):
    comment = IssueComment(issue=issue, project=issue.project, workspace=issue.workspace, actor=author)
    comment.comment_html = "<p>hello</p>"
    comment.save(created_by_id=author.id)
    return comment


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("entity_type", WORK_ITEM_ENTITY_TYPES)
class TestLegacyWorkItemUpload:
    def test_a_restricted_guest_cannot_upload_to_a_hidden_work_item(self, setup, entity_type):
        hidden = _legacy_upload(setup["guest"], setup, entity_type, setup["hidden_issue"].id)
        missing = _legacy_upload(setup["guest"], setup, entity_type, uuid4())

        assert hidden.status_code == missing.status_code == status.HTTP_404_NOT_FOUND
        assert hidden.data == missing.data
        assert not FileAsset.all_objects.filter(issue=setup["hidden_issue"]).exists()

    def test_a_restricted_guest_still_uploads_to_their_own_work_item(self, setup, entity_type):
        response = _legacy_upload(setup["guest"], setup, entity_type, setup["guest_issue"].id)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        asset = FileAsset.objects.get(id=response.data["id"])
        assert (asset.project_id, asset.issue_id) == (setup["project"].id, setup["guest_issue"].id)

    def test_a_member_still_uploads_to_the_work_item(self, setup, entity_type):
        response = _legacy_upload(setup["member"], setup, entity_type, setup["hidden_issue"].id)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert FileAsset.objects.get(id=response.data["id"]).issue_id == setup["hidden_issue"].id


@pytest.mark.contract
@pytest.mark.django_db
class TestLegacyCommentImageUpload:
    COMMENT = FileAsset.EntityTypeContext.COMMENT_DESCRIPTION

    def test_the_author_still_uploads_into_their_comment(self, setup):
        comment = _comment(setup["hidden_issue"], setup["member"])

        response = _legacy_upload(setup["member"], setup, self.COMMENT, comment.id)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        asset = FileAsset.objects.get(id=response.data["id"])
        assert (asset.project_id, asset.comment_id) == (setup["project"].id, comment.id)

    def test_a_project_admin_still_uploads_into_another_users_comment(self, setup):
        comment = _comment(setup["hidden_issue"], setup["member"])

        response = _legacy_upload(setup["admin"], setup, self.COMMENT, comment.id)

        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_a_member_cannot_upload_into_another_users_comment(self, setup):
        comment = _comment(setup["hidden_issue"], setup["admin"])

        response = _legacy_upload(setup["member"], setup, self.COMMENT, comment.id)
        missing = _legacy_upload(setup["member"], setup, self.COMMENT, uuid4())

        assert response.status_code == missing.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == missing.data
        assert not FileAsset.objects.filter(comment=comment).exists()

    def test_a_restricted_guest_cannot_upload_into_a_comment_on_a_hidden_work_item(self, setup):
        # The guest's own comment, so this is refused by the visibility rule.
        comment = _comment(setup["hidden_issue"], setup["guest"])

        response = _legacy_upload(setup["guest"], setup, self.COMMENT, comment.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert not FileAsset.objects.filter(comment=comment).exists()


def _soft_deleted(asset):
    asset.is_deleted = True
    asset.deleted_at = timezone.now()
    asset.save(update_fields=["is_deleted", "deleted_at"])
    return asset


def _v2_delete(user, setup, asset):
    url = ASSET_URL.format(slug=setup["workspace"].slug, project_id=setup["project"].id, pk=asset.id)
    return _client(user).delete(url)


def _v2_complete(user, setup, asset):
    url = ASSET_URL.format(slug=setup["workspace"].slug, project_id=setup["project"].id, pk=asset.id)
    with mock.patch("plane.app.views.asset.v2.complete_asset_upload") as complete:
        response = _client(user).patch(url, {}, format="json")
    return response, complete


def _v2_restore(user, setup, asset):
    return _client(user).post(RESTORE_URL.format(slug=setup["workspace"].slug, asset_id=asset.id))


def _legacy_delete(user, asset):
    return _client(user).delete(LEGACY_ASSET_URL.format(asset_key=asset.asset.name))


def _legacy_restore(user, asset):
    return _client(user).post(LEGACY_RESTORE_URL.format(asset_key=asset.asset.name))


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("entity_type", WORK_ITEM_ENTITY_TYPES)
class TestWorkItemAssetMutation:
    """The guest's own upload on a work item that is now hidden from them, for
    example one written before the project turned off guest_view_all_features."""

    def test_a_restricted_guest_cannot_delete_it(self, setup, entity_type):
        asset = _asset(setup["project"], setup["guest"], entity_type, setup["hidden_issue"])

        assert _v2_delete(setup["guest"], setup, asset).status_code == status.HTTP_404_NOT_FOUND
        assert _legacy_delete(setup["guest"], asset).status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.deleted_at is None

    def test_a_restricted_guest_cannot_restore_it(self, setup, entity_type):
        asset = _soft_deleted(_asset(setup["project"], setup["guest"], entity_type, setup["hidden_issue"]))

        assert _v2_restore(setup["guest"], setup, asset).status_code == status.HTTP_404_NOT_FOUND
        assert _legacy_restore(setup["guest"], asset).status_code == status.HTTP_404_NOT_FOUND
        assert FileAsset.all_objects.get(id=asset.id).deleted_at is not None

    def test_a_restricted_guest_cannot_complete_it(self, setup, entity_type):
        asset = _asset(setup["project"], setup["guest"], entity_type, setup["hidden_issue"])

        response, complete = _v2_complete(setup["guest"], setup, asset)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        complete.assert_not_called()

    def test_a_restricted_guest_still_changes_one_on_their_own_work_item(self, setup, entity_type):
        asset = _asset(setup["project"], setup["guest"], entity_type, setup["guest_issue"])

        response, complete = _v2_complete(setup["guest"], setup, asset)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        complete.assert_called_once()
        assert _v2_delete(setup["guest"], setup, asset).status_code == status.HTTP_204_NO_CONTENT
        assert _v2_restore(setup["guest"], setup, asset).status_code == status.HTTP_204_NO_CONTENT
        assert _legacy_delete(setup["guest"], asset).status_code == status.HTTP_204_NO_CONTENT
        assert _legacy_restore(setup["guest"], asset).status_code == status.HTTP_204_NO_CONTENT

    def test_the_uploading_member_still_changes_it(self, setup, entity_type):
        asset = _asset(setup["project"], setup["member"], entity_type, setup["hidden_issue"])

        response, complete = _v2_complete(setup["member"], setup, asset)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        complete.assert_called_once()
        assert _v2_delete(setup["member"], setup, asset).status_code == status.HTTP_204_NO_CONTENT
        assert _v2_restore(setup["member"], setup, asset).status_code == status.HTTP_204_NO_CONTENT
        assert _legacy_delete(setup["member"], asset).status_code == status.HTTP_204_NO_CONTENT
        assert _legacy_restore(setup["member"], asset).status_code == status.HTTP_204_NO_CONTENT

    def test_a_project_admin_still_changes_another_users_asset(self, setup, entity_type):
        asset = _asset(setup["project"], setup["guest"], entity_type, setup["hidden_issue"])

        assert _v2_delete(setup["admin"], setup, asset).status_code == status.HTTP_204_NO_CONTENT
        assert _v2_restore(setup["admin"], setup, asset).status_code == status.HTTP_204_NO_CONTENT
        assert _legacy_delete(setup["admin"], asset).status_code == status.HTTP_204_NO_CONTENT
        assert _legacy_restore(setup["admin"], asset).status_code == status.HTTP_204_NO_CONTENT
