# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ReadTimeoutError
from django.test import override_settings

from plane.mailer.exceptions import MailAcceptanceUnknownError, MailConfigurationError
from plane.mailer.transports.ses import SESAPITransport
from plane.mailer.transports.smtp import SMTPTransport


def _message():
    message = EmailMessage()
    message["From"] = "Hangar <hello@hangar.example.com>"
    message["To"] = "person@example.com"
    message["Subject"] = "Test"
    message.set_content("Body")
    return message


@pytest.mark.unit
@override_settings(
    EMAIL_SES_REGION="eu-central-1",
    EMAIL_SES_AWS_ACCESS_KEY_ID="",
    EMAIL_SES_AWS_SECRET_ACCESS_KEY="",
    EMAIL_SES_AWS_SESSION_TOKEN="",
)
def test_ses_api_uses_structured_configuration_and_returns_provider_id():
    client = MagicMock()
    client.send_email.return_value = {"MessageId": "ses-message-id"}
    with patch("plane.mailer.transports.ses._client", return_value=client):
        receipt = SESAPITransport().send(
            _message(),
            configuration_set="hangar-auth",
            message_tags={"outbox_id": "opaque", "mail_class": "account_access"},
        )

    request = client.send_email.call_args.kwargs
    assert request["ConfigurationSetName"] == "hangar-auth"
    assert {tag["Name"] for tag in request["EmailTags"]} == {"outbox_id", "mail_class"}
    assert receipt.provider_message_id == "ses-message-id"


@pytest.mark.unit
@override_settings(
    EMAIL_SES_REGION="eu-central-1",
    EMAIL_SES_AWS_ACCESS_KEY_ID="",
    EMAIL_SES_AWS_SECRET_ACCESS_KEY="",
    EMAIL_SES_AWS_SESSION_TOKEN="",
)
def test_ses_api_read_timeout_is_acceptance_unknown():
    client = MagicMock()
    client.send_email.side_effect = ReadTimeoutError(endpoint_url="https://email.eu-central-1.amazonaws.com")
    with patch("plane.mailer.transports.ses._client", return_value=client):
        with pytest.raises(MailAcceptanceUnknownError):
            SESAPITransport().send(_message())


@pytest.mark.unit
def test_ses_api_rejects_invalid_structured_tags_before_calling_aws():
    with patch("plane.mailer.transports.ses._client") as client:
        with pytest.raises(MailConfigurationError, match="tag"):
            SESAPITransport().send(_message(), message_tags={"unsafe tag": "value"})

    client.assert_not_called()


@pytest.mark.unit
@override_settings(EMAIL_PROVIDER="smtp", EMAIL_SMTP_TIMEOUT_SECONDS=5)
def test_generic_smtp_does_not_leak_ses_headers():
    client = MagicMock()
    client.send_message.return_value = {}
    with (
        patch(
            "plane.mailer.transports.smtp.get_email_configuration",
            return_value=("smtp.example.com", "user", "password", 587, "1", "0", "sender@example.com"),
        ),
        patch("plane.mailer.transports.smtp.smtplib.SMTP", return_value=client),
    ):
        message = _message()
        SMTPTransport().send(
            message,
            configuration_set="hangar-auth",
            message_tags={"outbox_id": "opaque"},
        )

    assert "X-SES-CONFIGURATION-SET" not in message
    assert "X-SES-MESSAGE-TAGS" not in message
