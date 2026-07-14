# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from django.utils import timezone

from plane.bgtasks.email_delivery_task import (
    cleanup_secure_email_records,
    consume_ses_email_events,
    dispatch_due_email_outbox,
)
from plane.db.models import EmailOutbox
from plane.mailer.enums import DeliveryMode, MailPolicyClass, OutboxStatus


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_DELIVERY_V2_ENABLED=True)
def test_due_dispatcher_recovers_a_missed_broker_publication():
    outbox = EmailOutbox.objects.create(
        recipient_email_ciphertext="encrypted",
        recipient_email_hash="a" * 64,
        policy_class=MailPolicyClass.ACCOUNT_ACCESS,
        template_key="auth.magic_signin",
        audit_label="Login code",
        sender="Hangar <hello@hangar.example.com>",
        delivery_mode=DeliveryMode.CLEAR,
        payload_ciphertext="encrypted",
        idempotency_key="test:due-dispatch",
        intent_digest="b" * 64,
        message_id="<due@hangar.example.com>",
        receipt_code="AAAA-BBBB-CCCC-DDDD-EEEE",
        status=OutboxStatus.QUEUED,
        next_attempt_at=timezone.now(),
    )
    with patch("plane.bgtasks.email_delivery_task.deliver_email_outbox.delay") as delay:
        dispatch_due_email_outbox()
    delay.assert_called_once_with(str(outbox.id))


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OUTBOX_RETENTION_DAYS=7, EMAIL_AUDIT_RETENTION_DAYS=90, EMAIL_EVENT_RETENTION_DAYS=4)
def test_cleanup_purges_payload_but_retains_recent_audit_receipt():
    outbox = EmailOutbox.objects.create(
        recipient_email_ciphertext="encrypted",
        recipient_email_hash="c" * 64,
        policy_class=MailPolicyClass.ACCOUNT_ACCESS,
        template_key="auth.magic_signin",
        audit_label="Login code",
        sender="Hangar <hello@hangar.example.com>",
        delivery_mode=DeliveryMode.CLEAR,
        payload_ciphertext="encrypted-payload",
        idempotency_key="test:audit-retention",
        intent_digest="d" * 64,
        message_id="<retention@hangar.example.com>",
        receipt_code="1111-2222-3333-4444-5555",
        status=OutboxStatus.ACCEPTED,
    )
    EmailOutbox.objects.filter(pk=outbox.id).update(created_at=timezone.now() - timedelta(days=8))

    cleanup_secure_email_records()

    outbox.refresh_from_db()
    assert outbox.payload_ciphertext == ""
    assert outbox.receipt_code == "1111-2222-3333-4444-5555"


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize("delivery_status", [OutboxStatus.ACCEPTED, OutboxStatus.ACCEPTANCE_UNKNOWN])
@override_settings(EMAIL_OUTBOX_RETENTION_DAYS=7, EMAIL_AUDIT_RETENTION_DAYS=90, EMAIL_EVENT_RETENTION_DAYS=4)
def test_cleanup_deletes_nonterminal_provider_receipts_after_audit_retention(delivery_status):
    outbox = EmailOutbox.objects.create(
        recipient_email_ciphertext="encrypted",
        recipient_email_hash="e" * 64,
        policy_class=MailPolicyClass.ACCOUNT_ACCESS,
        template_key="auth.magic_signin",
        audit_label="Login code",
        sender="Hangar <hello@hangar.example.com>",
        delivery_mode=DeliveryMode.CLEAR,
        payload_ciphertext="",
        idempotency_key=f"test:expired-audit:{delivery_status}",
        intent_digest="f" * 64,
        message_id=f"<expired-{delivery_status}@hangar.example.com>",
        receipt_code=(
            "AAAA-1111-BBBB-2222-CCCC" if delivery_status == OutboxStatus.ACCEPTED else "DDDD-3333-EEEE-4444-FFFF"
        ),
        status=delivery_status,
    )
    EmailOutbox.objects.filter(pk=outbox.id).update(created_at=timezone.now() - timedelta(days=91))

    cleanup_secure_email_records()

    assert not EmailOutbox.all_objects.filter(pk=outbox.id).exists()


@pytest.mark.unit
@override_settings(EMAIL_DELIVERY_V2_ENABLED=True, EMAIL_SES_EVENTS_QUEUE_URL="https://sqs.example/queue")
def test_invalid_sqs_event_is_not_deleted_so_redrive_can_quarantine_it():
    client = MagicMock()
    client.receive_message.side_effect = [
        {
            "Messages": [
                {
                    "MessageId": "poison",
                    "ReceiptHandle": "receipt-handle",
                    "Body": "not-json",
                    "Attributes": {"ApproximateReceiveCount": "4"},
                }
            ]
        },
        {"Messages": []},
    ]

    with patch("plane.bgtasks.email_delivery_task._sqs_client", return_value=client):
        consume_ses_email_events()

    client.delete_message.assert_not_called()
