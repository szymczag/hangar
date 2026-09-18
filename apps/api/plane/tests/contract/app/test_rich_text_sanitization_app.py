# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Write paths that stored rich-text HTML without the shared allowlist.

Page create and page edit took `description_html` from the request as it
came. A comment posted on a published Spaces board is sanitized, but went
through the app serializer with the whole request body, so anyone signed in
could also set fields only a project member should (`external_source`, ...).
"""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import DeployBoard, Issue, IssueComment, Page, Project, ProjectMember, State

HOSTILE_HTML = (
    '<p style="position:fixed;inset:0;z-index:99999">overlay</p>'
    "<img src=x onerror=alert(1)><script>alert(2)</script>"
    '<span data-text-color="red;position:fixed">colour</span>'
)


def assert_sanitized(html):
    assert "<script" not in html
    assert "onerror" not in html
    assert "style=" not in html
    assert "position:fixed" not in html


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Sanitized", identifier=f"S{uuid4().hex[:4]}", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20, is_active=True)
    return project


@pytest.mark.contract
@pytest.mark.django_db
class TestPageDescriptionHtml:
    def pages_url(self, workspace, project):
        return f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/"

    def test_create_sanitizes_description_html(self, session_client, workspace, project):
        with mock.patch("plane.app.views.page.base.page_transaction.delay") as transaction:
            response = session_client.post(
                self.pages_url(workspace, project),
                {"name": "Page", "description_html": HOSTILE_HTML},
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        stored = Page.objects.get(pk=response.data["id"]).description_html
        assert_sanitized(stored)
        assert "overlay" in stored
        # The page log is built from what was stored, not from the request.
        assert_sanitized(transaction.call_args.kwargs["new_description_html"])

    def test_update_sanitizes_description_html(self, session_client, workspace, project):
        with mock.patch("plane.app.views.page.base.page_transaction.delay"):
            created = session_client.post(self.pages_url(workspace, project), {"name": "Page"}, format="json")
            response = session_client.patch(
                f"{self.pages_url(workspace, project)}{created.data['id']}/",
                {"description_html": HOSTILE_HTML},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert_sanitized(Page.objects.get(pk=created.data["id"]).description_html)


@pytest.fixture
def board(db, workspace, create_user, project):
    state = State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)
    issue = Issue.objects.create(
        name="Public", workspace=workspace, project=project, state=state, created_by=create_user
    )
    deploy_board = DeployBoard.objects.create(
        entity_name="project",
        entity_identifier=project.id,
        project=project,
        workspace=workspace,
        is_comments_enabled=True,
    )
    return {"issue": issue, "anchor": deploy_board.anchor}


@pytest.mark.contract
@pytest.mark.django_db
class TestSpacesCommentHtml:
    def comments_url(self, board):
        return f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/comments/"

    def test_create_sanitizes_and_ignores_privileged_fields(self, session_client, board, create_user):
        with mock.patch("plane.space.views.issue.issue_activity"):
            response = session_client.post(
                self.comments_url(board),
                {"comment_html": HOSTILE_HTML, "access": "INTERNAL", "external_source": "forged"},
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        comment = IssueComment.objects.get(pk=response.data["id"])
        assert_sanitized(comment.comment_html)
        assert comment.access == "EXTERNAL"
        assert comment.external_source is None
        assert comment.actor_id == create_user.id

    def test_update_sanitizes_and_ignores_privileged_fields(self, session_client, board, create_user):
        comment = IssueComment.objects.create(
            issue=board["issue"],
            project=board["issue"].project,
            workspace=board["issue"].workspace,
            comment_html="<p>original</p>",
            access="EXTERNAL",
            actor=create_user,
            created_by=create_user,
        )
        with mock.patch("plane.space.views.issue.issue_activity"):
            response = session_client.patch(
                f"{self.comments_url(board)}{comment.id}/",
                {"comment_html": HOSTILE_HTML, "external_id": "forged"},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert_sanitized(comment.comment_html)
        assert comment.external_id is None
