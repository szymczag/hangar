# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest
from rest_framework import status

from plane.db.models import Cycle, Issue, IssueLink, Project, ProjectMember


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Update guards",
        identifier="GUARD",
        workspace=workspace,
        created_by=create_user,
        cycle_view=True,
    )
    ProjectMember.objects.create(
        workspace=workspace,
        project=project,
        member=create_user,
        role=20,
        is_active=True,
    )
    return project


@pytest.fixture
def issue_link(project, create_user):
    issue = Issue.objects.create(
        name="Linked issue",
        project=project,
        workspace=project.workspace,
        created_by=create_user,
    )
    link = IssueLink.objects.create(
        title="Original title",
        url="https://example.com/original",
        issue=issue,
        project=project,
        workspace=project.workspace,
        created_by=create_user,
    )
    return issue, link


def link_url(workspace, project, issue, link):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/links/{link.id}/"


@pytest.mark.contract
@pytest.mark.django_db
class TestCycleAndLinkUpdateGuards:
    def test_cycle_without_end_date_is_rejected_instead_of_raising(
        self, api_key_client, workspace, project, create_user
    ):
        cycle = Cycle.objects.create(
            name="No end",
            project=project,
            workspace=workspace,
            owned_by=create_user,
        )
        url = f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/cycles/{cycle.id}/archive/"

        response = api_key_client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"error": "Only completed cycles can be archived"}
        cycle.refresh_from_db()
        assert cycle.archived_at is None

    @patch("plane.api.views.issue.issue_activity.delay")
    @patch("plane.api.views.issue.crawl_work_item_link_title.delay")
    def test_title_only_link_update_does_not_recrawl(
        self, crawl_delay, activity_delay, api_key_client, workspace, project, issue_link
    ):
        issue, link = issue_link

        response = api_key_client.patch(
            link_url(workspace, project, issue, link),
            {"title": "Updated title"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        crawl_delay.assert_not_called()

    @patch("plane.api.views.issue.issue_activity.delay")
    @patch("plane.api.views.issue.crawl_work_item_link_title.delay")
    def test_changed_link_url_is_crawled_once(
        self, crawl_delay, activity_delay, api_key_client, workspace, project, issue_link
    ):
        issue, link = issue_link
        updated_url = "https://example.com/updated"

        response = api_key_client.patch(
            link_url(workspace, project, issue, link),
            {"url": updated_url},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        crawl_delay.assert_called_once_with(link.id, updated_url)

    @patch("plane.api.views.issue.issue_activity.delay")
    @patch("plane.api.views.issue.crawl_work_item_link_title.delay")
    def test_empty_link_url_is_not_crawled(
        self, crawl_delay, activity_delay, api_key_client, workspace, project, issue_link
    ):
        issue, link = issue_link

        response = api_key_client.patch(
            link_url(workspace, project, issue, link),
            {"url": ""},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        crawl_delay.assert_not_called()
