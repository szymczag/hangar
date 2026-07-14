# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings

from plane.db.models import EmailOutbox, UserOpenPGPKey
from plane.mailer.enums import DeliveryMode, OpenPGPKeyStatus, OutboxStatus
from plane.mailer.exceptions import MailAcceptanceUnknownError, MailPolicyError, MailRetryableError
from plane.mailer.service import enqueue_rendered_email, render_outbox_message
from plane.mailer.transports import TransportReceipt
from plane.tests.factories import UserFactory

SECURE_SETTINGS = override_settings(
    EMAIL_DELIVERY_V2_ENABLED=True,
    EMAIL_OPENPGP_ENABLED=False,
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
        patch("plane.mailer.service.get_transport") as get_transport,
    ):
        get_transport.return_value.send.return_value = TransportReceipt("ses-clear-message")
        result = enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code",
            text_body="Code 1234",
            idempotency_key="test:clear-account-mail",
        )

    outbox = EmailOutbox.objects.get(pk=result.outbox_id)
    assert outbox.status == OutboxStatus.ACCEPTED
    assert outbox.delivery_mode == DeliveryMode.CLEAR
    assert bytes(outbox.encrypted_message) == b""
    assert len(outbox.receipt_code.split("-")) == 5
    assert outbox.audit_label == "Login code"
    sent_message = get_transport.return_value.send.call_args.args[0]
    assert "Code 1234" in sent_message.get_body(preferencelist=("plain",)).get_content()
    assert outbox.provider_message_id == "ses-clear-message"


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
@pytest.mark.parametrize(
    ("transport_error", "expected_status"),
    [
        (MailRetryableError("endpoint unavailable"), OutboxStatus.FAILED_PERMANENT),
        (MailAcceptanceUnknownError("response lost"), OutboxStatus.ACCEPTANCE_UNKNOWN),
    ],
)
def test_clear_account_mail_failure_is_recorded_without_retry_or_content(transport_error, expected_status):
    user = UserFactory(email="clear-failure@example.com")
    with (
        patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"),
        patch("plane.mailer.service.get_transport") as get_transport,
    ):
        get_transport.return_value.send.side_effect = transport_error
        result = enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="auth.magic_signin",
            subject="Login code",
            text_body="ONE-TIME-SECRET",
            idempotency_key=f"test:clear-failure:{expected_status}",
        )

    outbox = EmailOutbox.objects.get(pk=result.outbox_id)
    assert outbox.status == expected_status
    assert outbox.next_attempt_at is None
    assert outbox.lease_expires_at is None
    assert bytes(outbox.encrypted_message) == b""
    assert get_transport.return_value.send.call_count == 1


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
    assert bytes(outbox.encrypted_message) == b""


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
def test_idempotent_clear_mail_is_never_resent_or_persisted():
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
        patch("plane.mailer.service.get_transport") as get_transport,
    ):
        get_transport.return_value.send.return_value = TransportReceipt("ses-idempotent")
        first = enqueue_rendered_email(text_body="First secret", **kwargs)
        replay = enqueue_rendered_email(text_body="Second secret", **kwargs)

    outbox = EmailOutbox.objects.get(pk=first.outbox_id)
    assert replay.outbox_id == first.outbox_id
    assert bytes(outbox.encrypted_message) == b""
    assert get_transport.return_value.send.call_count == 1


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
def test_corrupt_openpgp_message_fails_closed():
    user = UserFactory(email="schema@example.com")
    key = UserOpenPGPKey.objects.create(
        user=user,
        version=1,
        certificate="public certificate",
        primary_fingerprint="A" * 40,
        encryption_subkey_fingerprint="B" * 40,
        primary_algorithm="RSA",
        encryption_algorithm="RSA",
        encryption_key_size=3072,
        status=OpenPGPKeyStatus.ACTIVE,
    )
    outbox = EmailOutbox.objects.create(
        recipient=user,
        recipient_email=user.email,
        policy_class="project_notification",
        template_key="notification.issue_updates",
        audit_label="Work item updates",
        sender="Hangar <hello@hangar.example.com>",
        delivery_mode=DeliveryMode.OPENPGP,
        encrypted_message=b"not a PGP/MIME message",
        idempotency_key="test:corrupt-openpgp",
        message_id="<corrupt@hangar.example.com>",
        receipt_code="AAAA-BBBB-CCCC-DDDD-EEEE",
        openpgp_key=key,
        openpgp_fingerprint=key.encryption_subkey_fingerprint,
        status=OutboxStatus.QUEUED,
    )

    with pytest.raises(MailPolicyError, match="integrity validation"):
        render_outbox_message(outbox)


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
@SECURE_SETTINGS
def test_openpgp_content_is_encrypted_before_outbox_persistence():
    user = UserFactory(email="encrypted@example.com")
    key = UserOpenPGPKey.objects.create(
        user=user,
        version=1,
        certificate="public certificate",
        primary_fingerprint="C" * 40,
        encryption_subkey_fingerprint="D" * 40,
        primary_algorithm="RSA",
        encryption_algorithm="RSA",
        encryption_key_size=3072,
        status=OpenPGPKeyStatus.ACTIVE,
    )
    with (
        override_settings(EMAIL_OPENPGP_ENABLED=True),
        patch("plane.mailer.service._configured_sender", return_value="Hangar <hello@hangar.example.com>"),
        patch("plane.mailer.mime.encrypt_for_certificate", return_value="PGP-CIPHERTEXT"),
        patch("plane.bgtasks.email_delivery_task.deliver_email_outbox.delay") as dispatch,
    ):
        result = enqueue_rendered_email(
            recipient_email=user.email,
            recipient_user=user,
            template_key="notification.issue_updates",
            subject="Confidential subject",
            text_body="CONFIDENTIAL_BODY_SENTINEL",
            idempotency_key="test:encrypted-before-storage",
        )

    outbox = EmailOutbox.objects.get(pk=result.outbox_id)
    stored = bytes(outbox.encrypted_message)
    assert b"CONFIDENTIAL_BODY_SENTINEL" not in stored
    assert b"Confidential subject" not in stored
    assert b"PGP-CIPHERTEXT" in stored
    assert outbox.openpgp_key == key
    dispatch.assert_called_once_with(str(outbox.id))


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
@SECURE_SETTINGS
@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"recipient_email": "not-an-email"}, "recipient email"),
        ({"idempotency_key": ""}, "idempotency key"),
        ({"expires_in": timedelta(0)}, "expiry window"),
    ],
)
def test_invalid_delivery_metadata_is_rejected_before_persistence(overrides, error):
    user = UserFactory(email="validation@example.com")
    kwargs = {
        "recipient_email": user.email,
        "recipient_user": user,
        "template_key": "auth.magic_signin",
        "subject": "Login code",
        "text_body": "Code",
        "idempotency_key": "test:validated-metadata",
    }
    kwargs.update(overrides)

    with pytest.raises(MailPolicyError, match=error):
        enqueue_rendered_email(**kwargs)

    assert not EmailOutbox.objects.exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(
    EMAIL_DELIVERY_V2_ENABLED=False,
    EMAIL_OPENPGP_ENABLED=False,
    EMAIL_PROVIDER="smtp",
    EMAIL_MESSAGE_ID_DOMAIN="hangar.example.com",
    EMAIL_REPLY_TO="",
    EMAIL_SES_CONFIGURATION_SET_AUTH="hangar-auth",
    EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS="hangar-notifications",
    EMAIL_MAX_ATTACHMENT_BYTES=1024,
    EMAIL_MAX_STORED_PAYLOAD_BYTES=4096,
)
def test_legacy_delivery_sends_directly_without_outbox():
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
