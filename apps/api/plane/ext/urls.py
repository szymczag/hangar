# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Fork API endpoints, mounted under /api/ alongside plane.app.urls.

from django.urls import path

from plane.ext.views.epic import (
    EpicDetailViewSet,
    EpicIssuesEndpoint,
    EpicSettingsEndpoint,
    EpicViewSet,
    IssueTypeListEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epic-settings/",
        EpicSettingsEndpoint.as_view(),
        name="epic-settings",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/",
        IssueTypeListEndpoint.as_view(),
        name="issue-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/",
        EpicViewSet.as_view(),
        name="epics",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:pk>/",
        EpicDetailViewSet.as_view(),
        name="epic-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epics/<uuid:pk>/issues/",
        EpicIssuesEndpoint.as_view(),
        name="epic-issues",
    ),
]
