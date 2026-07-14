# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
from unittest.mock import patch

import pytest
from django.test import override_settings

from plane.db.models import EmailOutbox
from plane.mailer.enums import DeliveryMode, OutboxStatus
from plane.mailer.exceptions import MailPolicyError
from plane.mailer.service import enqueue_rendered_email, render_outbox_message
from plane.tests.factories import UserFactory

KEY = base64.urlsafe_b64encode(b"o" * 32).decode("ascii")
LOOKUP_KEY = base64.urlsafe_b64encode(b"l" * 32).decode("ascii")
SECURE_SETTINGS = override_settings(
    EMAIL_DELIVERY_V2_ENABLED=True,
    EMAIL_OPENPGP_ENABLED=False,
    EMAIL_OUTBOX_ENCRYPTION_KEYS=f"v1:{KEY}",
    EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY,
    EMAIL_MESSAGE_ID_DOMAIN="hangar.example.com",
    EMAIL_REPLY_TO="",
    EMAIL_SES_CONFIGURATION_SET_AUTH="hangar-auth",
    EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS="hangar-notifications",
    EMAIL_MAX_ATTACHMENT_BYTES=1024,
    EMAIL_MAX_STORED_PAYLOAD_BYTES=4096,
)


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
def test_clear_account_mail_creates_a_receipted_outbox_row():
    user = UserFactory(email="person@example.com")
    with (
        patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"),
        patch("plane.bgtasks.email_delivery_task.deliver_email_outbox.delay") as dispatch,
    ):
        result = enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code",
            text_body="Code 1234",
            idempotency_key="test:clear-account-mail",
        )

    outbox = EmailOutbox.objects.get(pk=result.outbox_id)
    assert outbox.status == OutboxStatus.QUEUED
    assert outbox.delivery_mode == DeliveryMode.CLEAR
    assert len(outbox.receipt_code.split("-")) == 5
    assert outbox.audit_label == "Login code"
    dispatch.assert_called_once_with(str(outbox.id))


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
def test_confidential_mail_without_key_is_a_payload_free_audit_receipt():
    user = UserFactory(email="person@example.com")
    with patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"):
        with override_settings(EMAIL_OPENPGP_ENABLED=True):
            result = enqueue_rendered_email(
                recipient_email=user.email,
                recipient_user=user,
                template_key="notification.issue_updates",
                subject="Secret project",
                text_body="Secret body",
                idempotency_key="test:suppressed-notification",
            )

    outbox = EmailOutbox.objects.get(pk=result.outbox_id)
    assert outbox.status == OutboxStatus.SUPPRESSED_NO_KEY
    assert outbox.delivery_mode == DeliveryMode.SUPPRESSED
    assert outbox.payload_ciphertext == ""


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
def test_idempotency_key_cannot_alias_a_different_payload():
    user = UserFactory(email="person@example.com")
    kwargs = {
        "recipient_email": user.email,
        "recipient_user": user,
        "template_key": "auth.magic_signin",
        "subject": "Login code",
        "idempotency_key": "test:conflicting-intent",
    }
    with (
        patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"),
        patch("plane.bgtasks.email_delivery_task.deliver_email_outbox.delay"),
    ):
        enqueue_rendered_email(text_body="First", **kwargs)
        with pytest.raises(MailPolicyError, match="idempotency key"):
            enqueue_rendered_email(text_body="Second", **kwargs)


@pytest.mark.unit
@pytest.mark.django_db
@SECURE_SETTINGS
def test_recipient_user_must_own_recipient_address():
    user = UserFactory(email="owner@example.com")
    with pytest.raises(MailPolicyError, match="does not own"):
        enqueue_rendered_email(
            recipient_email="other@example.com",
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code",
            text_body="Code",
        )


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
def test_unknown_payload_schema_fails_closed():
    user = UserFactory(email="schema@example.com")
    with (
        patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"),
        patch("plane.bgtasks.email_delivery_task.deliver_email_outbox.delay"),
    ):
        result = enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code",
            text_body="Code",
            idempotency_key="test:unknown-schema",
        )
    outbox = EmailOutbox.objects.get(pk=result.outbox_id)
    outbox.payload_schema_version = 99

    with pytest.raises(MailPolicyError, match="schema"):
        render_outbox_message(outbox)


@pytest.mark.unit
@pytest.mark.django_db
@SECURE_SETTINGS
def test_header_injection_is_rejected_before_persistence():
    user = UserFactory(email="headers@example.com")
    with pytest.raises(MailPolicyError, match="subject"):
        enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code\r\nBcc: attacker@example.com",
            text_body="Code",
        )

    assert not EmailOutbox.objects.exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(
    EMAIL_DELIVERY_V2_ENABLED=False,
    EMAIL_OPENPGP_ENABLED=False,
    EMAIL_OUTBOX_ENCRYPTION_KEYS="",
    EMAIL_LOOKUP_HMAC_KEY="",
    EMAIL_PROVIDER="smtp",
    EMAIL_MESSAGE_ID_DOMAIN="hangar.example.com",
    EMAIL_REPLY_TO="",
    EMAIL_SES_CONFIGURATION_SET_AUTH="hangar-auth",
    EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS="hangar-notifications",
    EMAIL_MAX_ATTACHMENT_BYTES=1024,
    EMAIL_MAX_STORED_PAYLOAD_BYTES=4096,
)
def test_legacy_delivery_sends_directly_without_secure_delivery_keys():
    user = UserFactory(email="legacy@example.com")
    with (
        patch("plane.mailer.service.get_transport") as get_transport,
        patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"),
    ):
        result = enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code",
            text_body="Code 1234",
        )

    assert result.outbox_id is None
    assert result.status == OutboxStatus.ACCEPTED
    assert not EmailOutbox.objects.exists()
    get_transport.assert_called_once_with("smtp")
    sent_message = get_transport.return_value.send.call_args.args[0]
    assert sent_message["To"] == user.email
    assert "Hangar email receipt" not in sent_message.get_body(preferencelist=("plain",)).get_content()
