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
    SAMLAuthInitiateEndpoint,
    SAMLCallbackEndpoint,
    SAMLMetadataEndpoint,
)
from plane.ext.views.capacity import GoogleCalendarCallbackEndpoint

urlpatterns = [
    path("google/calendar/callback/", GoogleCalendarCallbackEndpoint.as_view(), name="google-calendar-callback"),
    path("oidc/", OIDCAuthInitiateEndpoint.as_view(), name="oidc-initiate"),
    path("oidc/callback/", OIDCCallbackEndpoint.as_view(), name="oidc-callback"),
    path("spaces/oidc/", OIDCAuthInitiateSpaceEndpoint.as_view(), name="oidc-space-initiate"),
    path("spaces/oidc/callback/", OIDCCallbackSpaceEndpoint.as_view(), name="oidc-space-callback"),
    path("saml/", SAMLAuthInitiateEndpoint.as_view(), name="saml-initiate"),
    path("saml/callback/", SAMLCallbackEndpoint.as_view(), name="saml-callback"),
    path("saml/metadata/", SAMLMetadataEndpoint.as_view(), name="saml-metadata"),
]
