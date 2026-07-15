# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings

from plane.license.api.views.configuration import InstanceConfigurationEndpoint
from plane.license.api.views.email_delivery import InstanceEmailDeliveryConfigurationEndpoint


@pytest.mark.unit
@override_settings(
    EMAIL_PROVIDER="ses_api",
    EMAIL_DELIVERY_V2_ENABLED=True,
    EMAIL_OPENPGP_ENABLED=True,
    EMAIL_REPLY_TO="support@example.com",
    EMAIL_SES_REGION="eu-central-1",
    EMAIL_SES_ACCOUNT_ID="123456789012",
    EMAIL_SES_AWS_ACCESS_KEY_ID="AKIAEXAMPLE",
    EMAIL_SES_AWS_SECRET_ACCESS_KEY="secret-access-key",
    EMAIL_SES_AWS_SESSION_TOKEN="session-token",
    EMAIL_SES_CONFIGURATION_SET_AUTH="hangar-auth",
    EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS="hangar-notifications",
    EMAIL_SES_EVENTS_QUEUE_URL="https://sqs.eu-central-1.amazonaws.com/123456789012/hangar-mail-events",
    EMAIL_SES_EVENTS_TOPIC_ARN="arn:aws:sns:eu-central-1:123456789012:hangar-mail-events",
)
def test_email_delivery_status_exposes_effective_ses_configuration_without_secrets():
    with patch(
        "plane.license.api.views.email_delivery.get_email_configuration",
        return_value=("", "", "", "", "", "", "Hangar <hello@hangar.example.com>"),
    ):
        response = InstanceEmailDeliveryConfigurationEndpoint().get(SimpleNamespace())

    assert response.status_code == 200
    assert response.data == {
        "provider": "ses_api",
        "is_deployment_managed": True,
        "durable_delivery_enabled": True,
        "openpgp_enabled": True,
        "sender": "Hangar <hello@hangar.example.com>",
        "reply_to": "support@example.com",
        "ses": {
            "region": "eu-central-1",
            "account_id": "123456789012",
            "access_key_id": "AKIAEXAMPLE",
            "auth_configuration_set": "hangar-auth",
            "notification_configuration_set": "hangar-notifications",
            "events_queue_url": "https://sqs.eu-central-1.amazonaws.com/123456789012/hangar-mail-events",
            "events_topic_arn": "arn:aws:sns:eu-central-1:123456789012:hangar-mail-events",
        },
    }
    assert "secret-access-key" not in str(response.data)
    assert "session-token" not in str(response.data)


@pytest.mark.unit
@override_settings(EMAIL_PROVIDER="smtp", EMAIL_DELIVERY_V2_ENABLED=False, EMAIL_OPENPGP_ENABLED=False)
def test_email_delivery_status_marks_smtp_as_instance_managed():
    with patch(
        "plane.license.api.views.email_delivery.get_email_configuration",
        return_value=("smtp.example.com", "", "", "587", "1", "0", "Hangar <hello@example.com>"),
    ):
        response = InstanceEmailDeliveryConfigurationEndpoint().get(SimpleNamespace())

    assert response.status_code == 200
    assert response.data["provider"] == "smtp"
    assert response.data["is_deployment_managed"] is False
    assert response.data["ses"] is None


@pytest.mark.unit
@override_settings(EMAIL_PROVIDER="ses_api")
def test_instance_configuration_rejects_smtp_updates_when_ses_api_is_managed():
    response = InstanceConfigurationEndpoint().patch(
        SimpleNamespace(data={"EMAIL_HOST": "smtp.example.com"}, user=SimpleNamespace(is_anonymous=True))
    )

    assert response.status_code == 409
    assert response.data == {
        "error": "SMTP settings are unavailable while Amazon SES API delivery is deployment managed."
    }
