# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A published board serves only the images it shows.

The board's asset GET needs no session. It serves:

- a description image of a work item the board shows (``issue_objects``);
- a comment image bound to a comment the board shows: EXTERNAL, comments
  enabled, on a work item the board shows;
- a board upload that is not bound yet, to its uploader only;
- an older unbound comment image that a shown comment by its uploader embeds.

Everything else, among them an image pending in the app and an image of an
INTERNAL comment, gets the same 404 as a missing id.
"""

from unittest import mock
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    DeployBoard,
    FileAsset,
    Issue,
    IssueComment,
    Page,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
)
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

READ_URL = "/api/public/assets/v2/anchor/{anchor}/{pk}/"
UPLOAD_URL = "/api/public/assets/v2/anchor/{anchor}/"
BULK_URL = "/api/public/assets/v2/anchor/{anchor}/{entity_id}/bulk/"
COMMENT_URL = "/api/public/anchor/{anchor}/issues/{issue_id}/comments/"


def _user(prefix):
    unique = uuid4().hex[:8]
    return User.objects.create(email=f"{prefix}-{unique}@plane.so", username=f"{prefix}_{unique}")


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _issue(project, state, author, **fields):
    return Issue.objects.create(
        name="Issue", workspace=project.workspace, project=project, state=state, created_by=author, **fields
    )


def _comment(issue, actor, access="EXTERNAL", html="<p>comment</p>"):
    return IssueComment.objects.create(
        issue=issue,
        project=issue.project,
        workspace=issue.workspace,
        comment_html=html,
        access=access,
        actor=actor,
    )


def _asset(project, owner, entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION, **fields):
    asset = FileAsset(
        attributes={"name": "image.png", "type": "image/png", "size": 10},
        asset=f"{project.workspace_id}/{uuid4().hex}-image.png",
        size=10,
        workspace=project.workspace,
        project_id=project.id,
        entity_type=entity_type,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
        **fields,
    )
    asset.save(created_by_id=owner.id)
    return asset


@pytest.fixture(autouse=True)
def _empty_throttle():
    """Anonymous requests share one throttle bucket; leave it as it was found."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def storage():
    with mock.patch("plane.space.views.asset.S3Storage") as storage_class:
        storage_class.return_value.generate_presigned_url.return_value = "https://signed.example/image"
        storage_class.return_value.generate_presigned_post.return_value = {"url": "https://s3.test/", "fields": {}}
        yield storage_class.return_value


@pytest.fixture
def setup(db, workspace, create_user):
    project = Project.objects.create(name="Pub", identifier="PUB", workspace=workspace, created_by=create_user)
    state = State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)
    triage = State.objects.create(name="Triage", project=project, workspace=workspace, group="triage")
    board = DeployBoard.objects.create(
        workspace=workspace,
        project=project,
        entity_name="project",
        entity_identifier=project.id,
        is_comments_enabled=True,
    )
    commenter = _user("commenter")
    ProjectMember.objects.create(project=project, workspace=workspace, member=commenter, role=15, is_active=True)
    return {
        "board": board,
        "project": project,
        "owner": create_user,
        "commenter": commenter,
        "issue": _issue(project, state, create_user),
        "archived_issue": _issue(project, state, create_user, archived_at=timezone.now()),
        "draft_issue": _issue(project, state, create_user, is_draft=True),
        "triage_issue": _issue(project, triage, create_user),
    }


def _read(setup, asset, user=None):
    return _client(user).get(READ_URL.format(anchor=setup["board"].anchor, pk=asset.id))


def _served(response):
    return response.status_code == status.HTTP_302_FOUND


def _refused(response):
    return response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
@pytest.mark.django_db
class TestBoardServesWhatItShows:
    def test_an_image_of_a_shown_comment_is_served(self, setup):
        comment = _comment(setup["issue"], setup["commenter"])
        asset = _asset(setup["project"], setup["commenter"], comment=comment, issue=setup["issue"])

        assert _served(_read(setup, asset))

    def test_an_older_image_bound_without_a_work_item_is_served(self, setup):
        comment = _comment(setup["issue"], setup["commenter"])
        asset = _asset(setup["project"], setup["commenter"], comment=comment)

        assert _served(_read(setup, asset))

    def test_a_description_image_of_a_shown_work_item_is_served(self, setup):
        asset = _asset(
            setup["project"], setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION, issue=setup["issue"]
        )

        assert _served(_read(setup, asset))

    def test_an_unbound_board_upload_is_served_to_its_uploader(self, setup):
        asset = _asset(setup["project"], setup["commenter"])

        assert _served(_read(setup, asset, setup["commenter"]))

    def test_an_older_unbound_image_embedded_in_a_shown_comment_is_served(self, setup):
        asset = _asset(setup["project"], setup["commenter"])
        _comment(setup["issue"], setup["commenter"], html=f'<image-component src="{asset.id}"></image-component>')

        assert _served(_read(setup, asset))

    def test_a_board_comment_image_stays_visible_through_compose_and_save(self, setup):
        """The board's own flow: upload unbound, preview, save the comment, bind."""
        client = _client(setup["commenter"])
        anchor = setup["board"].anchor
        uploaded = client.post(
            UPLOAD_URL.format(anchor=anchor),
            {
                "name": "image.png",
                "type": "image/png",
                "size": 10,
                "entity_type": FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
                "entity_identifier": "",
            },
            format="json",
        )
        assert uploaded.status_code == status.HTTP_200_OK, uploaded.data
        asset = FileAsset.objects.get(id=uploaded.data["asset_id"])
        asset.is_uploaded = True
        asset.upload_validation_version = UPLOAD_VALIDATION_VERSION
        asset.save(update_fields=["is_uploaded", "upload_validation_version"])

        assert _served(_read(setup, asset, setup["commenter"]))
        assert _refused(_read(setup, asset))

        with mock.patch("plane.space.views.issue.issue_activity"):
            created = client.post(
                COMMENT_URL.format(anchor=anchor, issue_id=setup["issue"].id),
                {"comment_html": f'<image-component src="{asset.id}"></image-component>'},
                format="json",
            )
        assert created.status_code == status.HTTP_201_CREATED, created.data
        bound = client.post(
            BULK_URL.format(anchor=anchor, entity_id=created.data["id"]),
            {"asset_ids": [str(asset.id)]},
            format="json",
        )
        assert bound.status_code == status.HTTP_204_NO_CONTENT

        assert _served(_read(setup, asset))


@pytest.mark.contract
@pytest.mark.django_db
class TestBoardRefusesWhatItDoesNotShow:
    def test_an_image_pending_in_the_app_is_refused(self, setup):
        asset = _asset(setup["project"], setup["commenter"], issue=setup["issue"])

        assert _refused(_read(setup, asset))
        # Its uploader reads it in the app, not from the board.
        assert _refused(_read(setup, asset, setup["commenter"]))

    def test_an_unbound_board_upload_is_refused_anonymously(self, setup):
        asset = _asset(setup["project"], setup["commenter"])

        assert _refused(_read(setup, asset))

    def test_an_unbound_board_upload_is_refused_to_another_user(self, setup):
        other = _user("other")
        ProjectMember.objects.create(
            project=setup["project"], workspace=setup["project"].workspace, member=other, role=15, is_active=True
        )
        asset = _asset(setup["project"], setup["commenter"])

        assert _refused(_read(setup, asset, other))

    def test_an_unbound_board_upload_is_refused_to_a_former_member(self, setup):
        asset = _asset(setup["project"], setup["commenter"])
        ProjectMember.objects.filter(member=setup["commenter"]).update(is_active=False)

        assert _refused(_read(setup, asset, setup["commenter"]))

    def test_an_image_of_an_internal_comment_is_refused(self, setup):
        comment = _comment(setup["issue"], setup["commenter"], access="INTERNAL")
        asset = _asset(setup["project"], setup["commenter"], comment=comment, issue=setup["issue"])

        assert _refused(_read(setup, asset))

    def test_a_comment_image_is_refused_when_comments_are_disabled(self, setup):
        comment = _comment(setup["issue"], setup["commenter"])
        asset = _asset(setup["project"], setup["commenter"], comment=comment, issue=setup["issue"])
        DeployBoard.objects.filter(id=setup["board"].id).update(is_comments_enabled=False)

        assert _refused(_read(setup, asset))

    def test_an_image_of_a_deleted_comment_is_refused(self, setup):
        comment = _comment(setup["issue"], setup["commenter"])
        asset = _asset(setup["project"], setup["commenter"], comment=comment, issue=setup["issue"])
        IssueComment.all_objects.filter(id=comment.id).update(deleted_at=timezone.now())

        assert _refused(_read(setup, asset))

    @pytest.mark.parametrize("hidden", ["archived_issue", "draft_issue", "triage_issue"])
    def test_a_comment_image_on_a_work_item_off_the_board_is_refused(self, setup, hidden):
        comment = _comment(setup[hidden], setup["commenter"])
        asset = _asset(setup["project"], setup["commenter"], comment=comment, issue=setup[hidden])

        assert _refused(_read(setup, asset))

    @pytest.mark.parametrize("hidden", ["archived_issue", "draft_issue", "triage_issue"])
    def test_a_description_image_of_a_work_item_off_the_board_is_refused(self, setup, hidden):
        asset = _asset(
            setup["project"], setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION, issue=setup[hidden]
        )

        assert _refused(_read(setup, asset))

    def test_a_description_image_of_no_work_item_is_refused(self, setup):
        asset = _asset(setup["project"], setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION)

        assert _refused(_read(setup, asset))

    def test_an_unbound_image_embedded_by_someone_else_is_refused(self, setup):
        other = _user("other")
        asset = _asset(setup["project"], setup["commenter"])
        _comment(setup["issue"], other, html=f'<image-component src="{asset.id}"></image-component>')

        assert _refused(_read(setup, asset))

    def test_an_unbound_image_embedded_in_an_internal_comment_is_refused(self, setup):
        asset = _asset(setup["project"], setup["commenter"])
        _comment(
            setup["issue"],
            setup["commenter"],
            access="INTERNAL",
            html=f'<image-component src="{asset.id}"></image-component>',
        )

        assert _refused(_read(setup, asset))

    def test_a_pending_image_embedded_on_another_work_item_is_refused(self, setup):
        other_issue = _issue(setup["project"], setup["issue"].state, setup["owner"])
        asset = _asset(setup["project"], setup["commenter"], issue=other_issue)
        _comment(setup["issue"], setup["commenter"], html=f'<image-component src="{asset.id}"></image-component>')

        assert _refused(_read(setup, asset))

    def test_a_missing_id_and_a_hidden_image_get_the_same_answer(self, setup, storage):
        asset = _asset(setup["project"], setup["commenter"], issue=setup["issue"])

        hidden = _read(setup, asset)
        missing = _client().get(READ_URL.format(anchor=setup["board"].anchor, pk=uuid4()))

        assert hidden.status_code == missing.status_code == status.HTTP_404_NOT_FOUND
        assert hidden.data == missing.data
        storage.generate_presigned_url.assert_not_called()

    def test_an_asset_of_another_project_is_refused(self, setup):
        other = Project.objects.create(
            name="Other", identifier="OTH", workspace=setup["project"].workspace, created_by=setup["owner"]
        )
        state = State.objects.create(name="Todo", project=other, workspace=other.workspace, group="backlog")
        issue = _issue(other, state, setup["owner"])
        asset = _asset(other, setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION, issue=issue)

        assert _refused(_read(setup, asset))

    def test_an_asset_of_another_workspace_is_refused(self, setup):
        workspace = Workspace.objects.create(name="Elsewhere", owner=setup["owner"], slug=f"else-{uuid4().hex[:6]}")
        other = Project.objects.create(name="Other", identifier="OTH", workspace=workspace, created_by=setup["owner"])
        state = State.objects.create(name="Todo", project=other, workspace=workspace, group="backlog")
        issue = _issue(other, state, setup["owner"])
        asset = _asset(other, setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION, issue=issue)

        assert _refused(_read(setup, asset))

    def test_a_disabled_board_serves_nothing(self, setup):
        comment = _comment(setup["issue"], setup["commenter"])
        image = _asset(setup["project"], setup["commenter"], comment=comment, issue=setup["issue"])
        description = _asset(
            setup["project"], setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION, issue=setup["issue"]
        )
        DeployBoard.objects.filter(id=setup["board"].id).update(is_disabled=True)

        assert _refused(_read(setup, image))
        assert _refused(_read(setup, description))

    def test_a_soft_deleted_asset_is_refused(self, setup):
        asset = _asset(
            setup["project"], setup["owner"], FileAsset.EntityTypeContext.ISSUE_DESCRIPTION, issue=setup["issue"]
        )
        FileAsset.all_objects.filter(id=asset.id).update(is_deleted=True, deleted_at=timezone.now())

        assert _refused(_read(setup, asset))

    def test_an_attachment_of_a_shown_work_item_is_refused(self, setup):
        asset = _asset(
            setup["project"], setup["owner"], FileAsset.EntityTypeContext.ISSUE_ATTACHMENT, issue=setup["issue"]
        )

        assert _refused(_read(setup, asset))

    def test_a_page_image_is_refused(self, setup):
        page = Page.objects.create(name="Page", workspace=setup["project"].workspace, owned_by=setup["owner"])
        asset = _asset(setup["project"], setup["owner"], FileAsset.EntityTypeContext.PAGE_DESCRIPTION, page=page)

        assert _refused(_read(setup, asset))

    def test_an_older_embedded_image_on_an_archived_work_item_is_refused(self, setup):
        asset = _asset(setup["project"], setup["commenter"])
        _comment(
            setup["archived_issue"],
            setup["commenter"],
            html=f'<image-component src="{asset.id}"></image-component>',
        )

        assert _refused(_read(setup, asset))

    def test_an_older_embedded_image_is_refused_when_comments_are_disabled(self, setup):
        asset = _asset(setup["project"], setup["commenter"])
        _comment(setup["issue"], setup["commenter"], html=f'<image-component src="{asset.id}"></image-component>')
        DeployBoard.objects.filter(id=setup["board"].id).update(is_comments_enabled=False)

        assert _refused(_read(setup, asset))
