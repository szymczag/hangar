# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Fork authentication endpoints (OIDC, SAML), mounted under /auth/ alongside
# plane.authentication.urls.

from django.urls import path

from plane.ext.auth.views import (
    OIDCAuthInitiateEndpoint,
    OIDCCallbackEndpoint,
    OIDCAuthInitiateSpaceEndpoint,
    OIDCCallbackSpaceEndpoint,
)

urlpatterns = [
    path("oidc/", OIDCAuthInitiateEndpoint.as_view(), name="oidc-initiate"),
    path("oidc/callback/", OIDCCallbackEndpoint.as_view(), name="oidc-callback"),
    path("spaces/oidc/", OIDCAuthInitiateSpaceEndpoint.as_view(), name="oidc-space-initiate"),
    path("spaces/oidc/callback/", OIDCCallbackSpaceEndpoint.as_view(), name="oidc-space-callback"),
]
