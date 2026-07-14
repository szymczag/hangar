# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
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


class InstanceConfigurationEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    @cache_response(60 * 60 * 2, user=False)
    def get(self, request):
        instance_configurations = InstanceConfiguration.objects.all()
        serializer = InstanceConfigurationSerializer(instance_configurations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @invalidate_cache(path="/api/instances/configurations/", user=False)
    @invalidate_cache(path="/api/instances/", user=False)
    def patch(self, request):
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
