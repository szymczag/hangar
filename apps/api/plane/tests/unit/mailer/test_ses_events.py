import json
import uuid

import pytest
from django.test import override_settings

from plane.bgtasks.email_delivery_task import process_ses_event
from plane.db.models import EmailOutbox, EmailSuppression
from plane.mailer.enums import MailPolicyClass, OutboxStatus, SuppressionReason


def _event(outbox_id, bounce_type, *, provider_message_id=None, timestamp="2026-01-01T12:01:00Z"):
    event = {
        "eventType": "Bounce",
        "mail": {
            "messageId": provider_message_id or f"provider-{bounce_type}",
            "sendingAccountId": "123456789012",
            "timestamp": "2026-01-01T12:00:00Z",
            "tags": {"outbox_id": [str(outbox_id)]},
        },
        "bounce": {"bounceType": bounce_type, "timestamp": timestamp},
    }
    return json.dumps({"TopicArn": "arn:aws:sns:eu-central-1:123456789012:mail", "Message": json.dumps(event)})


@pytest.fixture
def accepted_outbox(db):
    identifier = uuid.uuid4()
    return EmailOutbox.objects.create(
        id=identifier,
        recipient_email_ciphertext="encrypted",
        recipient_email_hash="a" * 64,
        policy_class=MailPolicyClass.PROJECT_NOTIFICATION,
        template_key="notification.issue_updates",
        payload_ciphertext="encrypted",
        idempotency_key=f"test:{identifier}",
        message_id=f"<{identifier}@hangar.example.com>",
        status=OutboxStatus.ACCEPTED,
    )


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(
    EMAIL_SES_EVENTS_TOPIC_ARN="arn:aws:sns:eu-central-1:123456789012:mail",
    EMAIL_SES_ACCOUNT_ID="123456789012",
)
def test_transient_bounce_does_not_suppress_recipient(accepted_outbox):
    process_ses_event(_event(accepted_outbox.id, "Transient"))

    accepted_outbox.refresh_from_db()
    assert accepted_outbox.last_error_code == "ses_transient_bounce"
    assert not EmailSuppression.objects.filter(email_hash=accepted_outbox.recipient_email_hash).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(
    EMAIL_SES_EVENTS_TOPIC_ARN="arn:aws:sns:eu-central-1:123456789012:mail",
    EMAIL_SES_ACCOUNT_ID="123456789012",
)
def test_permanent_bounce_suppresses_and_purges_payload(accepted_outbox):
    process_ses_event(_event(accepted_outbox.id, "Permanent"))

    accepted_outbox.refresh_from_db()
    assert accepted_outbox.status == OutboxStatus.FAILED_PERMANENT
    assert accepted_outbox.payload_ciphertext == ""
    assert EmailSuppression.objects.filter(
        email_hash=accepted_outbox.recipient_email_hash,
        reason=SuppressionReason.HARD_BOUNCE,
        is_active=True,
    ).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(
    EMAIL_SES_EVENTS_TOPIC_ARN="arn:aws:sns:eu-central-1:123456789012:mail",
    EMAIL_SES_ACCOUNT_ID="123456789012",
)
def test_new_permanent_bounce_reactivates_suppression_after_operator_removal(accepted_outbox):
    EmailSuppression.objects.create(
        email_hash=accepted_outbox.recipient_email_hash,
        reason=SuppressionReason.HARD_BOUNCE,
        is_active=False,
        deactivation_reason="Address was previously corrected",
    )

    process_ses_event(_event(accepted_outbox.id, "Permanent"))

    assert EmailSuppression.objects.filter(
        email_hash=accepted_outbox.recipient_email_hash,
        reason=SuppressionReason.HARD_BOUNCE,
        is_active=True,
    ).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(
    EMAIL_SES_EVENTS_TOPIC_ARN="arn:aws:sns:eu-central-1:123456789012:mail",
    EMAIL_SES_ACCOUNT_ID="123456789012",
)
def test_older_event_cannot_regress_a_newer_delivery(accepted_outbox):
    provider_message_id = "provider-stable"
    delivery = {
        "eventType": "Delivery",
        "mail": {
            "messageId": provider_message_id,
            "sendingAccountId": "123456789012",
            "timestamp": "2026-01-01T12:00:00Z",
            "tags": {"outbox_id": [str(accepted_outbox.id)]},
        },
        "delivery": {"timestamp": "2026-01-01T12:05:00Z", "processingTimeMillis": 50},
    }
    process_ses_event(
        json.dumps(
            {
                "TopicArn": "arn:aws:sns:eu-central-1:123456789012:mail",
                "Message": json.dumps(delivery),
            }
        )
    )
    process_ses_event(
        _event(
            accepted_outbox.id,
            "Permanent",
            provider_message_id=provider_message_id,
            timestamp="2026-01-01T12:01:00Z",
        )
    )

    accepted_outbox.refresh_from_db()
    assert accepted_outbox.status == OutboxStatus.DELIVERED
    assert not EmailSuppression.objects.filter(email_hash=accepted_outbox.recipient_email_hash).exists()
