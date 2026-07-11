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
)
from plane.ext.views.issue_type import (
    IssuePropertiesEndpoint,
    IssuePropertyDetailEndpoint,
    IssuePropertyOptionDetailEndpoint,
    IssuePropertyOptionsEndpoint,
    IssuePropertyValuesEndpoint,
    IssueTypeDetailEndpoint,
    IssueTypesEndpoint,
)

PROJECT_BASE = "workspaces/<str:slug>/projects/<uuid:project_id>"

EPIC_BASE = "workspaces/<str:slug>/projects/<uuid:project_id>/epics"

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/epic-settings/",
        EpicSettingsEndpoint.as_view(),
        name="epic-settings",
    ),
    path(
        f"{PROJECT_BASE}/issue-types/",
        IssueTypesEndpoint.as_view(),
        name="issue-types",
    ),
    path(
        f"{PROJECT_BASE}/issue-types/<uuid:type_id>/",
        IssueTypeDetailEndpoint.as_view(),
        name="issue-type-detail",
    ),
    path(
        f"{PROJECT_BASE}/issue-types/<uuid:type_id>/properties/",
        IssuePropertiesEndpoint.as_view(),
        name="issue-type-properties",
    ),
    path(
        f"{PROJECT_BASE}/properties/<uuid:property_id>/",
        IssuePropertyDetailEndpoint.as_view(),
        name="issue-property-detail",
    ),
    path(
        f"{PROJECT_BASE}/properties/<uuid:property_id>/options/",
        IssuePropertyOptionsEndpoint.as_view(),
        name="issue-property-options",
    ),
    path(
        f"{PROJECT_BASE}/properties/<uuid:property_id>/options/<uuid:option_id>/",
        IssuePropertyOptionDetailEndpoint.as_view(),
        name="issue-property-option-detail",
    ),
    path(
        f"{PROJECT_BASE}/issues/<uuid:issue_id>/property-values/",
        IssuePropertyValuesEndpoint.as_view(),
        name="issue-property-values",
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
