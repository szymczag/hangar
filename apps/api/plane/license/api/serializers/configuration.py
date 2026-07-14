# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings

from plane.license.models import InstanceConfiguration

from .base import BaseSerializer

DEPLOYMENT_MANAGED_EMAIL_VALUES = {
    "EMAIL_PROVIDER": lambda: settings.EMAIL_PROVIDER,
    "EMAIL_DELIVERY_V2_ENABLED": lambda: "1" if settings.EMAIL_DELIVERY_V2_ENABLED else "0",
    "EMAIL_OPENPGP_ENABLED": lambda: "1" if settings.EMAIL_OPENPGP_ENABLED else "0",
    "EMAIL_SES_REGION": lambda: settings.EMAIL_SES_REGION,
}


class InstanceConfigurationSerializer(BaseSerializer):
    class Meta:
        model = InstanceConfiguration
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.key in DEPLOYMENT_MANAGED_EMAIL_VALUES:
            data["value"] = DEPLOYMENT_MANAGED_EMAIL_VALUES[instance.key]()
        # Secret configuration is write-only. Never return SMTP credentials to a browser.
        if instance.is_encrypted:
            data["value"] = ""
            data["is_configured"] = bool(instance.value)

        return data
