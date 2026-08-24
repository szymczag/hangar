# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.license.api.views import (
    EmailCredentialCheckEndpoint,
    InstanceAdminEndpoint,
    InstanceAdminSignInEndpoint,
    InstanceUserEndpoint,
    InstanceAdminSignUpEndpoint,
    InstanceConfigurationEndpoint,
    DisableEmailFeatureEndpoint,
    InstanceEndpoint,
    InstanceTelemetryEndpoint,
    SignUpScreenVisitedEndpoint,
    InstanceAdminUserMeEndpoint,
    InstanceAdminSignOutEndpoint,
    InstanceAdminUserSessionEndpoint,
    InstanceWorkSpaceAvailabilityCheckEndpoint,
    InstanceWorkSpaceEndpoint,
    InstanceEmailDeliveryConfigurationEndpoint,
    InstanceEmailDeliveryLogEndpoint,
    InstanceEmailSuppressionEndpoint,
)

# Fork (see FORK.md): these must stay under /api/instances/ — the session
# middleware picks the admin cookie by that substring in the path.
from plane.ext.views.instance_webauthn import (  # noqa: E402
    AdminWebAuthnAuthenticationOptionsEndpoint,
    AdminWebAuthnAuthenticationVerifyEndpoint,
    AdminWebAuthnCredentialsEndpoint,
    AdminWebAuthnRegistrationOptionsEndpoint,
    AdminWebAuthnRegistrationVerifyEndpoint,
)

urlpatterns = [
    path(
        "admins/webauthn/authentication/options/",
        AdminWebAuthnAuthenticationOptionsEndpoint.as_view(),
        name="instance-admin-webauthn-authentication-options",
    ),
    path(
        "admins/webauthn/authentication/verify/",
        AdminWebAuthnAuthenticationVerifyEndpoint.as_view(),
        name="instance-admin-webauthn-authentication-verify",
    ),
    path(
        "admins/webauthn/registration/options/",
        AdminWebAuthnRegistrationOptionsEndpoint.as_view(),
        name="instance-admin-webauthn-registration-options",
    ),
    path(
        "admins/webauthn/registration/verify/",
        AdminWebAuthnRegistrationVerifyEndpoint.as_view(),
        name="instance-admin-webauthn-registration-verify",
    ),
    path(
        "admins/webauthn/credentials/",
        AdminWebAuthnCredentialsEndpoint.as_view(http_method_names=["get"]),
        name="instance-admin-webauthn-credentials",
    ),
    path(
        "admins/webauthn/credentials/<uuid:pk>/",
        AdminWebAuthnCredentialsEndpoint.as_view(http_method_names=["delete"]),
        name="instance-admin-webauthn-credential",
    ),
    path("", InstanceEndpoint.as_view(), name="instance"),
    path("telemetry/", InstanceTelemetryEndpoint.as_view(), name="instance-telemetry"),
    path("admins/", InstanceAdminEndpoint.as_view(), name="instance-admins"),
    path("admins/me/", InstanceAdminUserMeEndpoint.as_view(), name="instance-admins"),
    path(
        "admins/session/",
        InstanceAdminUserSessionEndpoint.as_view(),
        name="instance-admin-session",
    ),
    path(
        "admins/sign-out/",
        InstanceAdminSignOutEndpoint.as_view(),
        name="instance-admins",
    ),
    path("admins/<uuid:pk>/", InstanceAdminEndpoint.as_view(), name="instance-admins"),
    path(
        "configurations/",
        InstanceConfigurationEndpoint.as_view(),
        name="instance-configuration",
    ),
    path(
        "configurations/disable-email-feature/",
        DisableEmailFeatureEndpoint.as_view(),
        name="disable-email-configuration",
    ),
    path(
        "users/",
        InstanceUserEndpoint.as_view(),
        name="instance-users",
    ),
    path(
        "admins/sign-in/",
        InstanceAdminSignInEndpoint.as_view(),
        name="instance-admin-sign-in",
    ),
    path(
        "admins/sign-up/",
        InstanceAdminSignUpEndpoint.as_view(),
        name="instance-admin-sign-up",
    ),
    path(
        "admins/sign-up-screen-visited/",
        SignUpScreenVisitedEndpoint.as_view(),
        name="instance-sign-up",
    ),
    path(
        "email-credentials-check/",
        EmailCredentialCheckEndpoint.as_view(),
        name="email-credential-check",
    ),
    path(
        "email-delivery/",
        InstanceEmailDeliveryConfigurationEndpoint.as_view(),
        name="email-delivery-configuration",
    ),
    path("email-delivery-log/", InstanceEmailDeliveryLogEndpoint.as_view(), name="email-delivery-log"),
    path("email-suppressions/", InstanceEmailSuppressionEndpoint.as_view(), name="email-suppressions"),
    path(
        "workspace-slug-check/",
        InstanceWorkSpaceAvailabilityCheckEndpoint.as_view(),
        name="instance-workspace-availability",
    ),
    path("workspaces/", InstanceWorkSpaceEndpoint.as_view(), name="instance-workspace"),
]
