# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An image pasted into a comment that is not saved yet (#518).

The comment has no id while it is being written, and the asset API refuses an
empty ``entity_identifier``: an asset must name an existing record it belongs to.
The editor therefore uploads the image under the work item the comment is
written on. It is held there as a pending comment image, read under that work
item's visibility, and the bulk association binds it to the comment once the
comment exists.

That binding is where an asset could be moved onto a record its uploader may not
write, so it fails closed unless the caller uploaded every image, may edit the
comment, and each image is pending on the comment's own work item (or already
belongs to that comment).
"""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import FileAsset, Issue, IssueComment, Project, ProjectMember, User, WorkspaceMember

S3_STORAGE_PATH = "plane.app.views.asset.v2.S3Storage"
UPLOAD_URL = "/api/assets/v2/workspaces/{slug}/projects/{project_id}/"
BULK_URL = "/api/assets/v2/workspaces/{slug}/projects/{project_id}/{entity_id}/bulk/"
COMMENT_URL = "/api/workspaces/{slug}/projects/{project_id}/issues/{issue_id}/comments/"
DUPLICATE_URL = "/api/assets/v2/workspaces/{slug}/duplicate-assets/{asset_id}/"


def _user(role, workspace, *projects):
    user = User.objects.create(email=f"u-{uuid4().hex[:8]}@plane.so", username=uuid4().hex)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    for project in projects:
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


def _comment(issue, author):
    comment = IssueComment(issue=issue, project=issue.project, workspace=issue.workspace, actor=author)
    comment.comment_html = "<p>hello</p>"
    comment.save(created_by_id=author.id)
    return comment


@pytest.fixture
def setup(db, workspace, create_user):
    project = Project.objects.create(name="Alpha", identifier="ALP", workspace=workspace, created_by=create_user)
    other_project = Project.objects.create(name="Beta", identifier="BET", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(workspace=workspace, project=project, member=create_user, role=20)
    ProjectMember.objects.create(workspace=workspace, project=other_project, member=create_user, role=20)
    writer = _user(15, workspace, project, other_project)
    other = _user(15, workspace, project, other_project)
    return {
        "workspace": workspace,
        "project": project,
        "other_project": other_project,
        "writer": writer,
        "other": other,
        "issue": _issue(project, create_user),
        "sibling_issue": _issue(project, create_user, "Sibling"),
        "foreign_issue": _issue(other_project, create_user, "Elsewhere"),
    }


def _upload(client, workspace, project, **data):
    payload = {"name": "pasted.png", "type": "image/png", "size": 2048, **data}
    with mock.patch(S3_STORAGE_PATH) as storage:
        storage.return_value.generate_presigned_post.return_value = {"url": "https://s3.test/", "fields": {}}
        return client.post(UPLOAD_URL.format(slug=workspace.slug, project_id=project.id), payload, format="json")


def _pending_image(client, setup, issue=None):
    """Upload a pending comment image and mark it uploaded, as completion would."""
    issue = issue or setup["issue"]
    response = _upload(
        client,
        setup["workspace"],
        issue.project,
        entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
        entity_identifier=str(issue.id),
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    asset = FileAsset.objects.get(id=response.data["asset_id"])
    asset.is_uploaded = True
    asset.save(update_fields=["is_uploaded"])
    return asset


def _bind(client, setup, comment, asset_ids, project=None):
    project = project or comment.project
    return client.post(
        BULK_URL.format(slug=setup["workspace"].slug, project_id=project.id, entity_id=comment.id),
        {"asset_ids": [str(asset_id) for asset_id in asset_ids]},
        format="json",
    )


@pytest.mark.contract
@pytest.mark.django_db
class TestNewCommentImageUpload:
    def test_an_image_for_a_new_comment_uploads_under_its_work_item(self, setup):
        client = _client(setup["writer"])

        response = _upload(
            client,
            setup["workspace"],
            setup["project"],
            entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            entity_identifier=str(setup["issue"].id),
        )

        assert response.status_code == status.HTTP_200_OK
        asset = FileAsset.objects.get(id=response.data["asset_id"])
        assert asset.project_id == setup["project"].id
        assert asset.issue_id == setup["issue"].id
        assert asset.comment_id is None
        assert asset.created_by_id == setup["writer"].id

    def test_the_image_is_bound_to_the_comment_once_it_is_created(self, setup):
        client = _client(setup["writer"])
        asset = _pending_image(client, setup)

        with (
            mock.patch("plane.app.views.issue.comment.issue_activity"),
            mock.patch("plane.app.views.issue.comment.model_activity"),
        ):
            created = client.post(
                COMMENT_URL.format(
                    slug=setup["workspace"].slug, project_id=setup["project"].id, issue_id=setup["issue"].id
                ),
                {"comment_html": f'<p><image-component src="{asset.id}"></image-component></p>'},
                format="json",
            )
        assert created.status_code == status.HTTP_201_CREATED, created.data
        comment = IssueComment.objects.get(id=created.data["id"])

        response = _bind(client, setup, comment, [asset.id])

        assert response.status_code == status.HTTP_204_NO_CONTENT
        asset.refresh_from_db()
        assert asset.comment_id == comment.id
        assert asset.issue_id == setup["issue"].id

    def test_an_image_of_a_saved_comment_still_uploads_under_the_comment(self, setup):
        client = _client(setup["writer"])
        comment = _comment(setup["issue"], setup["writer"])

        response = _upload(
            client,
            setup["workspace"],
            setup["project"],
            entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            entity_identifier=str(comment.id),
        )

        assert response.status_code == status.HTTP_200_OK
        assert FileAsset.objects.get(id=response.data["asset_id"]).comment_id == comment.id

    def test_a_pending_image_cannot_be_bound_to_a_comment_on_another_work_item(self, setup):
        client = _client(setup["writer"])
        asset = _pending_image(client, setup)
        comment = _comment(setup["sibling_issue"], setup["writer"])

        response = _bind(client, setup, comment, [asset.id])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.comment_id is None
        assert asset.issue_id == setup["issue"].id

    def test_a_pending_image_cannot_be_bound_to_a_comment_in_another_project(self, setup):
        client = _client(setup["writer"])
        asset = _pending_image(client, setup)
        comment = _comment(setup["foreign_issue"], setup["writer"])

        # Through the comment's project: the asset is not in it.
        assert _bind(client, setup, comment, [asset.id]).status_code == status.HTTP_404_NOT_FOUND
        # Through the asset's project: the comment is not in it.
        assert (
            _bind(client, setup, comment, [asset.id], project=setup["project"]).status_code == status.HTTP_404_NOT_FOUND
        )
        asset.refresh_from_db()
        assert asset.comment_id is None
        assert asset.project_id == setup["project"].id

    def test_another_user_cannot_claim_a_pending_image(self, setup):
        asset = _pending_image(_client(setup["writer"]), setup)
        comment = _comment(setup["issue"], setup["other"])

        response = _bind(_client(setup["other"]), setup, comment, [asset.id])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.comment_id is None

    def test_an_image_cannot_be_bound_to_a_comment_its_uploader_may_not_edit(self, setup):
        client = _client(setup["writer"])
        asset = _pending_image(client, setup)
        comment = _comment(setup["issue"], setup["other"])

        response = _bind(client, setup, comment, [asset.id])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.comment_id is None

    def test_an_image_of_one_comment_cannot_be_moved_to_another(self, setup):
        client = _client(setup["writer"])
        asset = _pending_image(client, setup)
        first = _comment(setup["issue"], setup["writer"])
        second = _comment(setup["issue"], setup["writer"])
        assert _bind(client, setup, first, [asset.id]).status_code == status.HTTP_204_NO_CONTENT

        response = _bind(client, setup, second, [asset.id])

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.comment_id == first.id

    def test_bulk_association_does_not_bind_a_comment_image_to_a_work_item(self, setup):
        """Bulk only binds comment images to a comment, never re-anchors them."""
        client = _client(setup["writer"])
        asset = _pending_image(client, setup)

        response = client.post(
            BULK_URL.format(
                slug=setup["workspace"].slug, project_id=setup["project"].id, entity_id=setup["sibling_issue"].id
            ),
            {"asset_ids": [str(asset.id)]},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        asset.refresh_from_db()
        assert asset.issue_id == setup["issue"].id

    def test_a_work_item_of_another_project_is_not_an_anchor(self, setup):
        response = _upload(
            _client(setup["writer"]),
            setup["workspace"],
            setup["project"],
            entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            entity_identifier=str(setup["foreign_issue"].id),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert not FileAsset.objects.filter(issue=setup["foreign_issue"]).exists()

    def test_a_restricted_guest_anchors_only_to_their_own_work_item(self, setup, workspace):
        guest = _user(5, workspace, setup["project"])
        client = _client(guest)
        own_issue = _issue(setup["project"], guest, "Guest's own")

        foreign = _upload(
            client,
            workspace,
            setup["project"],
            entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            entity_identifier=str(setup["issue"].id),
        )
        own = _upload(
            client,
            workspace,
            setup["project"],
            entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            entity_identifier=str(own_issue.id),
        )

        assert foreign.status_code == status.HTTP_404_NOT_FOUND
        assert own.status_code == status.HTTP_200_OK

    def test_a_new_comment_can_take_a_copied_image(self, setup):
        """Pasting an existing image duplicates it, under the same work item anchor."""
        client = _client(setup["writer"])
        source = _pending_image(client, setup)
        duplicate = mock.Mock(id=uuid4())

        with (
            mock.patch(S3_STORAGE_PATH),
            mock.patch("plane.app.views.asset.v2.copyable_asset", return_value=source),
            mock.patch("plane.app.views.asset.v2.duplicate_file_asset", return_value=duplicate) as copy,
        ):
            response = client.post(
                DUPLICATE_URL.format(slug=setup["workspace"].slug, asset_id=source.id),
                {
                    "entity_type": FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
                    "entity_id": str(setup["issue"].id),
                    "project_id": str(setup["project"].id),
                },
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert copy.call_args.kwargs["entity_fields"] == {"issue_id": setup["issue"].id}


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "entity_type",
    [
        FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
        FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
        FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
    ],
)
@pytest.mark.parametrize("identifier", ["", "not-a-uuid", "123"])
def test_an_identifier_that_is_not_an_id_is_still_refused(setup, entity_type, identifier):
    response = _upload(
        _client(setup["writer"]),
        setup["workspace"],
        setup["project"],
        entity_type=entity_type,
        entity_identifier=identifier,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "entity_identifier" in response.data["error"]
    assert not FileAsset.objects.filter(created_by=setup["writer"]).exists()
