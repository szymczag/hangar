# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Saving a page records a version for the history panel.

`track_page_version` read `page.description`, a field upstream renamed to
`description_json` (makeplane/plane#8230) before the version task was
rewritten against the old name (makeplane/plane#8440). Every save raised
`AttributeError` inside the task, which logs and returns, so no
`PageVersion` row was ever written and the history panel stayed empty.
"""

from unittest import mock
from uuid import uuid4

import pytest
from rest_framework import status

from plane.bgtasks.page_version_task import track_page_version
from plane.db.models import Page, PageVersion, Project, ProjectMember, ProjectPage

FIRST_JSON = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "first"}]}]}
SECOND_JSON = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "second"}]}]}


@pytest.fixture
def page(db, workspace, create_user):
    project = Project.objects.create(
        name="Versions", identifier=f"V{uuid4().hex[:4]}", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20, is_active=True)
    page = Page.objects.create(workspace=workspace, owned_by=create_user, access=Page.PUBLIC_ACCESS, name="Page")
    ProjectPage.objects.create(workspace=workspace, project=project, page=page)
    return page, project


def run_task_inline(**kwargs):
    # The task swallows exceptions (log_exception), so it must run here, in the
    # request, for the assertions below to see whether it wrote anything.
    return track_page_version(**kwargs)


@pytest.mark.contract
@pytest.mark.django_db
class TestPageVersionHistory:
    def save(self, client, workspace, project, page, html, json_content):
        with (
            mock.patch("plane.app.views.page.base.page_transaction.delay"),
            mock.patch("plane.app.views.page.base.track_page_version.delay", side_effect=run_task_inline),
            mock.patch("plane.bgtasks.page_version_task.log_exception") as log_exception,
        ):
            response = client.patch(
                f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{page.id}/description/",
                {"description_html": html, "description_json": json_content},
                format="json",
            )
        assert response.status_code == status.HTTP_200_OK, response.data
        log_exception.assert_not_called()

    def test_save_records_a_version_with_the_saved_content(self, session_client, workspace, create_user, page):
        page, project = page

        self.save(session_client, workspace, project, page, "<p>first</p>", FIRST_JSON)

        versions = list(PageVersion.objects.filter(page=page))
        assert len(versions) == 1
        version = versions[0]
        assert version.description_html == "<p>first</p>"
        assert version.description_json == FIRST_JSON
        assert version.description_stripped == "first"
        assert version.owned_by_id == create_user.id
        assert version.workspace_id == workspace.id

    def test_a_second_save_within_the_window_updates_the_same_version(self, session_client, workspace, page):
        page, project = page

        self.save(session_client, workspace, project, page, "<p>first</p>", FIRST_JSON)
        self.save(session_client, workspace, project, page, "<p>second</p>", SECOND_JSON)

        versions = list(PageVersion.objects.filter(page=page))
        assert len(versions) == 1
        assert versions[0].description_html == "<p>second</p>"
        assert versions[0].description_json == SECOND_JSON

    def test_history_endpoint_lists_and_returns_the_recorded_version(self, session_client, workspace, page):
        page, project = page

        self.save(session_client, workspace, project, page, "<p>first</p>", FIRST_JSON)

        base = f"/api/workspaces/{workspace.slug}/projects/{project.id}/pages/{page.id}/versions/"
        listing = session_client.get(base)
        assert listing.status_code == status.HTTP_200_OK
        assert len(listing.data) == 1

        detail = session_client.get(f"{base}{listing.data[0]['id']}/")
        assert detail.status_code == status.HTTP_200_OK
        assert detail.data["description_html"] == "<p>first</p>"
        assert detail.data["description_json"] == FIRST_JSON
