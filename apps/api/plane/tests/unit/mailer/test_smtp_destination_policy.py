# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest
from django.test import override_settings

from plane.mailer.exceptions import MailConfigurationError
from plane.mailer.transports.smtp import SMTPTransport, _smtp_client


@override_settings(SMTP_ALLOWED_PORTS={25, 465, 587}, SMTP_ALLOWED_HOSTS=[], SMTP_ALLOWED_IPS=[])
def test_smtp_destination_policy_rejects_private_resolution():
    with patch(
        "plane.mailer.transports.smtp.resolve_and_validate",
        side_effect=ValueError("private"),
    ):
        with pytest.raises(MailConfigurationError, match="destination"):
            _smtp_client("smtp.internal", 587, timeout=5, ssl_enabled=False)


@override_settings(SMTP_ALLOWED_PORTS={25, 465, 587}, SMTP_ALLOWED_HOSTS=[], SMTP_ALLOWED_IPS=[])
def test_smtp_destination_policy_rejects_unapproved_port():
    with pytest.raises(MailConfigurationError, match="port"):
        _smtp_client("smtp.example.com", 8080, timeout=5, ssl_enabled=False)


@override_settings(EMAIL_PROVIDER="smtp")
def test_smtp_credentials_require_tls():
    with patch(
        "plane.mailer.transports.smtp.get_email_configuration",
        return_value=("smtp.example.com", "user", "password", 587, "0", "0", "sender@example.com"),
    ):
        with pytest.raises(MailConfigurationError, match="require TLS"):
            SMTPTransport().send(object())
