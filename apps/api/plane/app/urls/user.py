# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import (
    AccountEndpoint,
    ProfileEndpoint,
    UpdateUserOnBoardedEndpoint,
    UpdateUserTourCompletedEndpoint,
    UserActivityEndpoint,
    UserActivityGraphEndpoint,
    ## User
    UserEndpoint,
    UserIssueCompletedGraphEndpoint,
    UserWorkspaceDashboardEndpoint,
    UserSessionEndpoint,
    ## End User
    ## Workspaces
    UserWorkSpacesEndpoint,
)
from plane.app.views.user.email_security import (
    EmailSecurityChallengeEndpoint,
    EmailSecurityChallengeVerifyEndpoint,
    EmailSecurityKeyEndpoint,
    EmailSecurityKeyUploadEndpoint,
    EmailSecurityReceiptEndpoint,
    EmailSecurityStatusEndpoint,
    EmailSecurityTestEndpoint,
)

urlpatterns = [
    # User Profile
    path(
        "users/me/",
        UserEndpoint.as_view({"get": "retrieve", "patch": "partial_update", "delete": "deactivate"}),
        name="users",
    ),
    path("users/session/", UserSessionEndpoint.as_view(), name="user-session"),
    path(
        "users/me/settings/",
        UserEndpoint.as_view({"get": "retrieve_user_settings"}),
        name="users",
    ),
    path(
        "users/me/email/generate-code/",
        UserEndpoint.as_view({"post": "generate_email_verification_code"}),
        name="user-email-verify-code",
    ),
    path(
        "users/me/email/",
        UserEndpoint.as_view({"patch": "update_email"}),
        name="user-email-update",
    ),
    # Profile
    path("users/me/profile/", ProfileEndpoint.as_view(), name="accounts"),
    path("users/me/email-security/", EmailSecurityStatusEndpoint.as_view(), name="email-security"),
    path(
        "users/me/email-security/receipts/",
        EmailSecurityReceiptEndpoint.as_view(),
        name="email-security-receipts",
    ),
    path("users/me/email-security/keys/", EmailSecurityKeyUploadEndpoint.as_view(), name="email-security-key-upload"),
    path(
        "users/me/email-security/keys/<uuid:key_id>/challenge/",
        EmailSecurityChallengeEndpoint.as_view(),
        name="email-security-key-challenge",
    ),
    path(
        "users/me/email-security/keys/<uuid:key_id>/verify/",
        EmailSecurityChallengeVerifyEndpoint.as_view(),
        name="email-security-key-verify",
    ),
    path(
        "users/me/email-security/keys/<uuid:key_id>/test/",
        EmailSecurityTestEndpoint.as_view(),
        name="email-security-key-test",
    ),
    path(
        "users/me/email-security/keys/<uuid:key_id>/",
        EmailSecurityKeyEndpoint.as_view(),
        name="email-security-key",
    ),
    # End profile
    # Accounts
    path("users/me/accounts/", AccountEndpoint.as_view(), name="accounts"),
    path("users/me/accounts/<uuid:pk>/", AccountEndpoint.as_view(), name="accounts"),
    ## End Accounts
    path(
        "users/me/instance-admin/",
        UserEndpoint.as_view({"get": "retrieve_instance_admin"}),
        name="users",
    ),
    path("users/me/onboard/", UpdateUserOnBoardedEndpoint.as_view(), name="user-onboard"),
    path(
        "users/me/tour-completed/",
        UpdateUserTourCompletedEndpoint.as_view(),
        name="user-tour",
    ),
    path("users/me/activities/", UserActivityEndpoint.as_view(), name="user-activities"),
    # user workspaces
    path("users/me/workspaces/", UserWorkSpacesEndpoint.as_view(), name="user-workspace"),
    # User Graphs
    path(
        "users/me/workspaces/<str:slug>/activity-graph/",
        UserActivityGraphEndpoint.as_view(),
        name="user-activity-graph",
    ),
    path(
        "users/me/workspaces/<str:slug>/issues-completed-graph/",
        UserIssueCompletedGraphEndpoint.as_view(),
        name="completed-graph",
    ),
    path(
        "users/me/workspaces/<str:slug>/dashboard/",
        UserWorkspaceDashboardEndpoint.as_view(),
        name="user-workspace-dashboard",
    ),
    ## End User Graph
]
