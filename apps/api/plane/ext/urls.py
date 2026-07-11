# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Fork API endpoints, mounted under /api/ alongside plane.app.urls.

from django.urls import path

from plane.app.views import (
    IssueActivityEndpoint,
    IssueAttachmentV2Endpoint,
    IssueCommentViewSet,
    IssueLinkViewSet,
    IssueReactionViewSet,
    IssueSubscriberViewSet,
    WorkItemDescriptionVersionEndpoint,
)

from plane.ext.views.epic import (
    EpicDetailViewSet,
    EpicIssuesEndpoint,
    EpicPaginatedViewSet,
    EpicSettingsEndpoint,
    EpicViewSet,
    IssueTypeListEndpoint,
)

EPIC_BASE = "workspaces/<str:slug>/projects/<uuid:project_id>/epics"

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
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/v2/epics/",
        EpicPaginatedViewSet.as_view({"get": "list"}),
        name="epics-paginated",
    ),
    # Epic sub-resources — the web issue services parameterize their URLs by
    # service type ("epics"), so these alias the existing work-item views,
    # none of which resolve the parent through the epic-excluding
    # issue_objects manager.
    path(f"{EPIC_BASE}/<uuid:issue_id>/history/", IssueActivityEndpoint.as_view(), name="epic-history"),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/comments/",
        IssueCommentViewSet.as_view({"get": "list", "post": "create"}),
        name="epic-comments",
    ),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/comments/<uuid:pk>/",
        IssueCommentViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="epic-comments",
    ),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/reactions/",
        IssueReactionViewSet.as_view({"get": "list", "post": "create"}),
        name="epic-reactions",
    ),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/reactions/<str:reaction_code>/",
        IssueReactionViewSet.as_view({"delete": "destroy"}),
        name="epic-reactions",
    ),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/subscribe/",
        IssueSubscriberViewSet.as_view(
            {"get": "subscription_status", "post": "subscribe", "delete": "unsubscribe"}
        ),
        name="epic-subscribe",
    ),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/links/",
        IssueLinkViewSet.as_view({"get": "list", "post": "create"}),
        name="epic-links",
    ),
    path(
        f"{EPIC_BASE}/<uuid:issue_id>/links/<uuid:pk>/",
        IssueLinkViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="epic-links",
    ),
    path(
        f"{EPIC_BASE}/<uuid:work_item_id>/description-versions/",
        WorkItemDescriptionVersionEndpoint.as_view(),
        name="epic-description-versions",
    ),
    path(
        f"{EPIC_BASE}/<uuid:work_item_id>/description-versions/<uuid:pk>/",
        WorkItemDescriptionVersionEndpoint.as_view(),
        name="epic-description-versions",
    ),
    path(
        f"assets/v2/{EPIC_BASE}/<uuid:issue_id>/attachments/",
        IssueAttachmentV2Endpoint.as_view(),
        name="epic-attachments",
    ),
    path(
        f"assets/v2/{EPIC_BASE}/<uuid:issue_id>/attachments/<uuid:pk>/",
        IssueAttachmentV2Endpoint.as_view(),
        name="epic-attachments",
    ),
    # Deferred epic routes (upstream views inline the epic-excluding
    # issue_objects manager and need dedicated ext variants):
    # epics-detail/, epics/list/, issue-relation/, archive/.
]
