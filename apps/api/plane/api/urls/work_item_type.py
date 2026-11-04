# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.api.views.work_item_type import (
    ImportWorkItemTypesAPIEndpoint,
    ProjectWorkItemTypeDetailAPIEndpoint,
    ProjectWorkItemTypeListCreateAPIEndpoint,
    WorkspaceWorkItemTypeDetailAPIEndpoint,
    WorkspaceWorkItemTypeListCreateAPIEndpoint,
)

urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/",
        ProjectWorkItemTypeListCreateAPIEndpoint.as_view(),
        name="work-item-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/work-item-types/<uuid:type_id>/",
        ProjectWorkItemTypeDetailAPIEndpoint.as_view(),
        name="work-item-type-detail",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/import-work-item-types/",
        ImportWorkItemTypesAPIEndpoint.as_view(),
        name="import-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/work-item-types/",
        WorkspaceWorkItemTypeListCreateAPIEndpoint.as_view(),
        name="workspace-work-item-types",
    ),
    path(
        "workspaces/<str:slug>/work-item-types/<uuid:type_id>/",
        WorkspaceWorkItemTypeDetailAPIEndpoint.as_view(),
        name="workspace-work-item-type-detail",
    ),
]
