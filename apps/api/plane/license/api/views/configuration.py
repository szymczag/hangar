# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import re
import uuid

# Django imports
from django.conf import settings
from django.db.models import Q, Case, When, Value

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from .base import BaseAPIView
from plane.license.api.permissions import InstanceAdminPermission
from plane.license.models import InstanceConfiguration
from plane.license.api.serializers import InstanceConfigurationSerializer
from plane.license.utils.encryption import encrypt_data
from plane.mailer.service import enqueue_rendered_email
from plane.utils.cache import cache_response, invalidate_cache

DEPLOYMENT_MANAGED_CONFIGURATION_KEYS = {"POSTHOG_HOST"}

# Reported to the admin panel so it can say where settings are actually read
# from. When SKIP_ENV_VAR is off the stored values are ignored at read time and
# the environment decides, which would otherwise make every form in the panel
# look editable while changing nothing.
COLOUR_CONFIGURATION_KEYS = {"INSTANCE_ACCENT_COLOR", "INSTANCE_LOGIN_BACKDROP_COLOR"}
CONFIGURATION_SOURCE_KEY = "CONFIGURATION_SOURCE"
CONFIGURATION_SOURCE_DATABASE = "database"
CONFIGURATION_SOURCE_ENVIRONMENT = "environment"

# Settings a deployment operator must own, because they widen where
# authentication traffic may be sent. Surfaced read-only so an admin looking
# for them in the panel finds out they exist and where they live, instead of
# concluding the instance cannot reach an internal provider.
ENVIRONMENT_ONLY_SETTINGS = (
    "GITEA_ALLOWED_IPS",
    "GITEA_ALLOWED_HOSTS",
    "GITLAB_ALLOWED_IPS",
    "GITLAB_ALLOWED_HOSTS",
)


def configuration_source():
    return CONFIGURATION_SOURCE_DATABASE if settings.SKIP_ENV_VAR else CONFIGURATION_SOURCE_ENVIRONMENT


class InstanceConfigurationEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    @cache_response(60 * 60 * 2, user=False)
    def get(self, request):
        instance_configurations = InstanceConfiguration.objects.exclude(key__in=DEPLOYMENT_MANAGED_CONFIGURATION_KEYS)
        serializer = InstanceConfigurationSerializer(instance_configurations, many=True)
        # Appended rather than returned alongside, so the response stays a flat
        # list of configuration entries and existing clients keep working.
        data = [
            *serializer.data,
            {
                "key": CONFIGURATION_SOURCE_KEY,
                "value": configuration_source(),
                "category": "META",
                "is_encrypted": False,
            },
        ]
        return Response(data, status=status.HTTP_200_OK)

    @invalidate_cache(path="/api/instances/configurations/", user=False)
    @invalidate_cache(path="/api/instances/", user=False)
    def patch(self, request):
        # With SKIP_ENV_VAR off, stored values are never read back: the
        # environment decides. Accepting the write would report success for a
        # change that has no effect, which is worse than refusing it.
        if not settings.SKIP_ENV_VAR:
            return Response(
                {
                    "error": (
                        "This instance reads its configuration from environment variables, so changes made here "
                        "would have no effect. Update the deployment environment instead, or unset SKIP_ENV_VAR=0 "
                        "to manage configuration from this panel."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Colours reach a style attribute on the sign-in page, which is the one
        # page that collects passwords. Anything but a plain hex colour is
        # refused here rather than escaped downstream, so there is one place to
        # look rather than several.
        for key in COLOUR_CONFIGURATION_KEYS & set(request.data):
            value = (request.data.get(key) or "").strip()
            if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                return Response(
                    {"error": f"{key} must be a colour such as #1d4ed8, or empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if CONFIGURATION_SOURCE_KEY in request.data:
            return Response(
                {"error": "Configuration source is reported by the deployment and cannot be set."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if set(ENVIRONMENT_ONLY_SETTINGS).intersection(request.data):
            return Response(
                {
                    "error": (
                        "Provider network allowlists are deployment-owned because they permit outbound "
                        "authentication traffic to private addresses. Set them as environment variables."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if DEPLOYMENT_MANAGED_CONFIGURATION_KEYS.intersection(request.data):
            return Response(
                {"error": "PostHog destination is managed by the deployment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        smtp_configuration_keys = {
            "EMAIL_HOST",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "EMAIL_PORT",
            "EMAIL_USE_TLS",
            "EMAIL_USE_SSL",
            "EMAIL_FROM",
            "ENABLE_SMTP",
        }
        if settings.EMAIL_PROVIDER == "ses_api" and smtp_configuration_keys.intersection(request.data):
            return Response(
                {"error": "SMTP settings are unavailable while Amazon SES API delivery is deployment managed."},
                status=status.HTTP_409_CONFLICT,
            )
        deployment_managed_email_keys = {
            "EMAIL_PROVIDER",
            "EMAIL_DELIVERY_V2_ENABLED",
            "EMAIL_OPENPGP_ENABLED",
            "EMAIL_SES_REGION",
        }
        if deployment_managed_email_keys.intersection(request.data):
            return Response(
                {"error": "Secure email transport settings are managed by the deployment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        normalized_values = {}
        if "OIDC_ALLOW_UNVERIFIED_EMAIL" in request.data:
            return Response(
                {"error": "Unverified OIDC email is not supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "GOOGLE_AUTH_MODE" in request.data or "GOOGLE_WORKSPACE_DOMAINS" in request.data:
            current = {
                item.key: item.value
                for item in InstanceConfiguration.objects.filter(
                    key__in=["GOOGLE_AUTH_MODE", "GOOGLE_WORKSPACE_DOMAINS"]
                )
            }
            mode = str(request.data.get("GOOGLE_AUTH_MODE", current.get("GOOGLE_AUTH_MODE", "generic"))).strip().lower()
            domains = str(
                request.data.get("GOOGLE_WORKSPACE_DOMAINS", current.get("GOOGLE_WORKSPACE_DOMAINS", ""))
            ).strip()
            try:
                domain_parse_failed = False
                normalized_domains = [
                    domain.strip().encode("idna").decode("ascii").lower()
                    for domain in domains.split(",")
                    if domain.strip()
                ]
            except UnicodeError:
                domain_parse_failed = True
                normalized_domains = []
            domains_valid = all(
                "." in domain
                and not domain.startswith((".", "-"))
                and not domain.endswith((".", "-"))
                and "/" not in domain
                and ":" not in domain
                for domain in normalized_domains
            )
            if (
                mode not in {"generic", "workspace"}
                or domain_parse_failed
                or not domains_valid
                or (mode == "workspace" and not normalized_domains)
            ):
                return Response(
                    {"error": "Google authentication mode must be generic, or workspace with allowed domains."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            normalized_values["GOOGLE_AUTH_MODE"] = mode
            normalized_values["GOOGLE_WORKSPACE_DOMAINS"] = ",".join(normalized_domains)

        configurations = InstanceConfiguration.objects.filter(key__in=request.data.keys())

        # A key with no stored row was previously dropped in silence: the
        # response was 200 listing everything except the key that did not
        # apply, so the panel reverted its control with nothing to show the
        # administrator. Refusing names the key instead, for the same reason
        # the environment-managed case above refuses rather than reporting a
        # success nothing will read.
        unknown_keys = sorted(set(request.data.keys()) - {row.key for row in configurations})
        if unknown_keys:
            return Response(
                {
                    "error": (
                        "This instance stores no configuration under "
                        f"{', '.join(unknown_keys)}, so the change was not saved. "
                        "The setting may belong to a newer version, or the instance "
                        "may need its configuration seeded."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        bulk_configurations = []
        for configuration in configurations:
            raw_value = normalized_values.get(
                configuration.key,
                request.data.get(configuration.key, configuration.value),
            )
            value = "" if raw_value is None else str(raw_value).strip()
            if configuration.is_encrypted:
                # An empty password means "keep the existing secret". This lets
                # the API remain write-only without erasing credentials when an
                # administrator edits another SMTP field.
                if not value:
                    continue
                configuration.value = encrypt_data(value)
            else:
                configuration.value = value
            bulk_configurations.append(configuration)

        InstanceConfiguration.objects.bulk_update(bulk_configurations, ["value"], batch_size=100)

        serializer = InstanceConfigurationSerializer(configurations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DisableEmailFeatureEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    @invalidate_cache(path="/api/instances/", user=False)
    def delete(self, request):
        if settings.EMAIL_DELIVERY_V2_ENABLED:
            return Response(
                {"error": "Secure email delivery is managed by the deployment."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            InstanceConfiguration.objects.filter(
                Q(
                    key__in=[
                        "EMAIL_HOST",
                        "EMAIL_HOST_USER",
                        "EMAIL_HOST_PASSWORD",
                        "ENABLE_SMTP",
                        "EMAIL_PORT",
                        "EMAIL_FROM",
                    ]
                )
            ).update(value=Case(When(key="ENABLE_SMTP", then=Value("0")), default=Value("")))
            return Response(status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "Failed to disable email configuration"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class EmailCredentialCheckEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def post(self, request):
        receiver_email = request.data.get("receiver_email", False)
        if not receiver_email:
            return Response(
                {"error": "Receiver email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = "Email Notification from Hangar"
        message = "This is a sample email notification sent from Hangar application."
        try:
            result = enqueue_rendered_email(
                template_key="diagnostic.test",
                idempotency_key=f"diagnostic-test:{request.user.id}:{uuid.uuid4()}",
                recipient_user=request.user if request.user.email.lower() == receiver_email.lower() else None,
                recipient_email=receiver_email,
                subject=subject,
                text_body=message,
            )
            return Response(
                {"message": "Email accepted for secure delivery.", "status": result.status},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception:
            return Response(
                {"error": "Could not send email. Please check your configuration"},
                status=status.HTTP_400_BAD_REQUEST,
            )
