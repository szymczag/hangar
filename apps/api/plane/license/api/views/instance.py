# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
import re

# Django imports
from django.conf import settings
from plane.mailer.configuration import is_email_delivery_configured

# Third party imports
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

# Module imports
from plane.app.views import BaseAPIView
from plane.db.models import Workspace
from plane.ext.product_metadata import get_product_metadata
from plane.license.api.permissions import InstanceAdminPermission
from plane.license.api.serializers import InstanceSerializer
from plane.license.models import Instance
from plane.utils.api_token_policy import api_token_minimum_role
from plane.utils.provider_profile import providers_managing_profiles
from plane.utils.visibility_policy import force_private_visibility
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.cache import cache_response, invalidate_cache
from plane.utils.otlp_endpoints import get_otlp_metric_export_configuration
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control


def _safe_colour(value) -> str:
    """Return the value only if it is a plain hex colour."""
    candidate = str(value or "").strip()
    return candidate if re.fullmatch(r"#[0-9a-fA-F]{6}", candidate) else ""


class InstanceEndpoint(BaseAPIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [InstanceAdminPermission()]
        return [AllowAny()]

    @cache_response(60 * 60 * 2, user=False)
    @method_decorator(cache_control(private=True, max_age=12))
    def get(self, request):
        instance = Instance.objects.first()

        # get the instance
        if instance is None:
            return Response(
                {
                    "is_activated": False,
                    "is_setup_done": False,
                    "product": get_product_metadata(),
                },
                status=status.HTTP_200_OK,
            )
        # Return instance
        serializer = InstanceSerializer(instance)
        data = serializer.data
        data["is_activated"] = True
        # Get all the configuration
        (
            ENABLE_SIGNUP,
            DISABLE_WORKSPACE_CREATION,
            IS_GOOGLE_ENABLED,
            GOOGLE_AUTO_REDIRECT,
            IS_GITHUB_ENABLED,
            GITHUB_APP_NAME,
            IS_GITLAB_ENABLED,
            IS_GITEA_ENABLED,
            EMAIL_HOST,
            ENABLE_MAGIC_LINK_LOGIN,
            ENABLE_EMAIL_PASSWORD,
            SLACK_CLIENT_ID,
            POSTHOG_API_KEY,
            UNSPLASH_ACCESS_KEY,
            LLM_API_KEY,
        ) = get_configuration_value(
            [
                {
                    "key": "ENABLE_SIGNUP",
                    "default": os.environ.get("ENABLE_SIGNUP", "0"),
                },
                {
                    "key": "DISABLE_WORKSPACE_CREATION",
                    "default": os.environ.get("DISABLE_WORKSPACE_CREATION", "0"),
                },
                {
                    "key": "IS_GOOGLE_ENABLED",
                    "default": os.environ.get("IS_GOOGLE_ENABLED", "0"),
                },
                {
                    "key": "GOOGLE_AUTO_REDIRECT",
                    "default": os.environ.get("GOOGLE_AUTO_REDIRECT", "0"),
                },
                {
                    "key": "IS_GITHUB_ENABLED",
                    "default": os.environ.get("IS_GITHUB_ENABLED", "0"),
                },
                {
                    "key": "GITHUB_APP_NAME",
                    "default": os.environ.get("GITHUB_APP_NAME", ""),
                },
                {
                    "key": "IS_GITLAB_ENABLED",
                    "default": os.environ.get("IS_GITLAB_ENABLED", "0"),
                },
                {
                    "key": "IS_GITEA_ENABLED",
                    "default": os.environ.get("IS_GITEA_ENABLED", "0"),
                },
                {"key": "EMAIL_HOST", "default": os.environ.get("EMAIL_HOST", "")},
                {
                    "key": "ENABLE_MAGIC_LINK_LOGIN",
                    "default": os.environ.get("ENABLE_MAGIC_LINK_LOGIN", "1"),
                },
                {
                    "key": "ENABLE_EMAIL_PASSWORD",
                    "default": os.environ.get("ENABLE_EMAIL_PASSWORD", "1"),
                },
                {
                    "key": "SLACK_CLIENT_ID",
                    "default": os.environ.get("SLACK_CLIENT_ID", None),
                },
                {
                    "key": "POSTHOG_API_KEY",
                    "default": os.environ.get("POSTHOG_API_KEY", None),
                },
                {
                    "key": "UNSPLASH_ACCESS_KEY",
                    "default": os.environ.get("UNSPLASH_ACCESS_KEY", ""),
                },
                {
                    "key": "LLM_API_KEY",
                    "default": os.environ.get("LLM_API_KEY", ""),
                },
            ]
        )

        data = {}
        data["product"] = get_product_metadata()
        # Authentication
        data["enable_signup"] = ENABLE_SIGNUP == "1"
        data["is_workspace_creation_disabled"] = DISABLE_WORKSPACE_CREATION == "1"
        data["is_google_enabled"] = IS_GOOGLE_ENABLED == "1"
        data["is_google_auto_redirect_enabled"] = GOOGLE_AUTO_REDIRECT == "1"
        data["is_github_enabled"] = IS_GITHUB_ENABLED == "1"
        data["is_gitlab_enabled"] = IS_GITLAB_ENABLED == "1"
        data["is_gitea_enabled"] = IS_GITEA_ENABLED == "1"
        data["is_magic_login_enabled"] = ENABLE_MAGIC_LINK_LOGIN == "1"
        data["is_email_password_enabled"] = ENABLE_EMAIL_PASSWORD == "1"

        # Fork (see FORK.md): extended authentication providers, resolved in a
        # separate call to keep this an append-only edit.
        (
            IS_OIDC_ENABLED,
            OIDC_PROVIDER_NAME,
            IS_SAML_ENABLED,
            SAML_PROVIDER_NAME,
        ) = get_configuration_value(
            [
                {
                    "key": "IS_OIDC_ENABLED",
                    "default": os.environ.get("IS_OIDC_ENABLED", "0"),
                },
                {
                    "key": "OIDC_PROVIDER_NAME",
                    "default": os.environ.get("OIDC_PROVIDER_NAME", "OIDC"),
                },
                {
                    "key": "IS_SAML_ENABLED",
                    "default": os.environ.get("IS_SAML_ENABLED", "0"),
                },
                {
                    "key": "SAML_PROVIDER_NAME",
                    "default": os.environ.get("SAML_PROVIDER_NAME", "SAML"),
                },
            ]
        )
        data["is_oidc_enabled"] = IS_OIDC_ENABLED == "1"
        data["oidc_provider_name"] = str(OIDC_PROVIDER_NAME)
        data["is_saml_enabled"] = IS_SAML_ENABLED == "1"
        data["saml_provider_name"] = str(SAML_PROVIDER_NAME)
        data["is_todoist_imports_enabled"] = settings.TODOIST_IMPORTS_ENABLED

        # Fork (see FORK.md): which providers overwrite a person's name and
        # avatar on every sign-in. The clients need this to stop offering an
        # edit that the next sign-in discards — see Adapter.sync_user_data.
        data["provider_managed_profiles"] = providers_managing_profiles()

        # Fork (see FORK.md): sign-in page branding. Served without a session,
        # because the page it dresses is seen before anyone has one. Empty
        # values mean the built-in wording and wordmark.
        (
            INSTANCE_BRANDING_NAME,
            INSTANCE_SIGN_IN_HEADER,
            INSTANCE_SIGN_IN_SUBHEADER,
            INSTANCE_LOGO_ASSET_ID,
        ) = get_configuration_value(
            [
                {"key": "INSTANCE_BRANDING_NAME", "default": os.environ.get("INSTANCE_BRANDING_NAME", "")},
                {"key": "INSTANCE_SIGN_IN_HEADER", "default": os.environ.get("INSTANCE_SIGN_IN_HEADER", "")},
                {"key": "INSTANCE_SIGN_IN_SUBHEADER", "default": os.environ.get("INSTANCE_SIGN_IN_SUBHEADER", "")},
                {"key": "INSTANCE_LOGO_ASSET_ID", "default": os.environ.get("INSTANCE_LOGO_ASSET_ID", "")},
            ]
        )
        data["branding_name"] = str(INSTANCE_BRANDING_NAME or "")
        data["sign_in_header"] = str(INSTANCE_SIGN_IN_HEADER or "")
        data["sign_in_subheader"] = str(INSTANCE_SIGN_IN_SUBHEADER or "")
        data["logo_url"] = f"/api/assets/v2/static/{INSTANCE_LOGO_ASSET_ID}/" if INSTANCE_LOGO_ASSET_ID else ""

        (
            INSTANCE_LOGIN_BACKGROUND_ASSET_ID,
            INSTANCE_ACCENT_COLOR,
            INSTANCE_LOGIN_BACKDROP_COLOR,
            INSTANCE_SHOW_LICENSE_NOTICE,
        ) = get_configuration_value(
            [
                {
                    "key": "INSTANCE_LOGIN_BACKGROUND_ASSET_ID",
                    "default": os.environ.get("INSTANCE_LOGIN_BACKGROUND_ASSET_ID", ""),
                },
                {"key": "INSTANCE_ACCENT_COLOR", "default": os.environ.get("INSTANCE_ACCENT_COLOR", "")},
                {
                    "key": "INSTANCE_LOGIN_BACKDROP_COLOR",
                    "default": os.environ.get("INSTANCE_LOGIN_BACKDROP_COLOR", ""),
                },
                {
                    "key": "INSTANCE_SHOW_LICENSE_NOTICE",
                    "default": os.environ.get("INSTANCE_SHOW_LICENSE_NOTICE", "1"),
                },
            ]
        )
        data["login_background_url"] = (
            f"/api/assets/v2/static/{INSTANCE_LOGIN_BACKGROUND_ASSET_ID}/" if INSTANCE_LOGIN_BACKGROUND_ASSET_ID else ""
        )
        # Re-checked on the way out as well as on the way in: a value written
        # before the validation existed, or straight into the database, must not
        # reach a style attribute.
        data["accent_color"] = _safe_colour(INSTANCE_ACCENT_COLOR)
        data["login_backdrop_color"] = _safe_colour(INSTANCE_LOGIN_BACKDROP_COLOR)
        data["show_license_notice"] = str(INSTANCE_SHOW_LICENSE_NOTICE) != "0"

        # Github app name
        data["github_app_name"] = str(GITHUB_APP_NAME)

        # Slack client
        data["slack_client_id"] = SLACK_CLIENT_ID

        # Posthog
        data["posthog_api_key"] = POSTHOG_API_KEY
        data["posthog_host"] = settings.POSTHOG_HOST

        # Unsplash
        data["has_unsplash_configured"] = bool(UNSPLASH_ACCESS_KEY)

        # Open AI settings
        data["has_llm_configured"] = bool(LLM_API_KEY)

        # Fork (see FORK.md): the workspace role an account needs before it may
        # mint an API token. Reported so the application can offer the feature
        # only where it would succeed, instead of accepting a form and answering
        # with a refusal it could have predicted. It discloses a policy an
        # operator set, not a credential.
        data["api_token_minimum_role"] = api_token_minimum_role()

        # Fork (see FORK.md): whether this instance forces everything private.
        # Reported so the clients stop offering a visibility choice that is not
        # accepted, and stop showing a publish action that is refused.
        data["force_private_visibility"] = force_private_visibility()

        # File size settings
        data["file_size_limit"] = float(os.environ.get("FILE_SIZE_LIMIT", 5242880))

        # is smtp configured
        data["is_smtp_configured"] = is_email_delivery_configured(EMAIL_HOST)

        # Base URL
        data["admin_base_url"] = settings.ADMIN_BASE_URL
        data["space_base_url"] = settings.SPACE_BASE_URL
        data["app_base_url"] = settings.APP_BASE_URL

        data["instance_changelog_url"] = settings.INSTANCE_CHANGELOG_URL
        data["is_self_managed"] = settings.IS_SELF_MANAGED
        instance_data = serializer.data
        instance_data["workspaces_exist"] = Workspace.objects.count() >= 1

        response_data = {"config": data, "instance": instance_data}
        return Response(response_data, status=status.HTTP_200_OK)

    @invalidate_cache(path="/api/instances/", user=False)
    def patch(self, request):
        # Get the instance
        instance = Instance.objects.first()
        serializer = InstanceSerializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            if (
                serializer.validated_data.get("is_telemetry_enabled")
                and not get_otlp_metric_export_configuration().is_configured
            ):
                return Response(
                    {
                        "is_telemetry_enabled": [
                            "Configure a valid OTLP collector in deployment settings before enabling telemetry."
                        ]
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InstanceTelemetryEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        configuration = get_otlp_metric_export_configuration()
        return Response(
            {
                "collector_configured": configuration.is_configured,
                "metrics_protocol": configuration.protocol if configuration.is_configured else None,
            },
            status=status.HTTP_200_OK,
        )


class SignUpScreenVisitedEndpoint(BaseAPIView):
    permission_classes = [AllowAny]

    @invalidate_cache(path="/api/instances/", user=False)
    def post(self, request):
        instance = Instance.objects.first()
        if instance is None:
            return Response(
                {"error": "Instance is not configured"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.is_signup_screen_visited = True
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
