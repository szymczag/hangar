# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Durable outbound email delivery and Amazon SES feedback consumption."""

import hashlib
import json
import logging
import random
import time
import uuid
from datetime import timedelta

import boto3
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from plane.db.models import (
    EmailDeliveryEvent,
    EmailNotificationLog,
    EmailOutbox,
    EmailSuppression,
    OpenPGPKeyChallenge,
    UserOpenPGPKey,
)
from plane.mailer.enums import DeliveryMode, OpenPGPKeyStatus, OutboxStatus, SuppressionReason
from plane.mailer.exceptions import MailAcceptanceUnknownError, MailPermanentError, MailRetryableError
from plane.mailer.service import render_outbox_message
from plane.mailer.transports import get_transport

logger = logging.getLogger("plane.worker")
MAX_DELIVERY_ATTEMPTS = 5
LEASE_DURATION = timedelta(minutes=5)
TERMINAL_STATUSES = {
    OutboxStatus.SUPPRESSED_PREFERENCE,
    OutboxStatus.SUPPRESSED_NO_KEY,
    OutboxStatus.SUPPRESSED_BOUNCE,
    OutboxStatus.SUPPRESSED_COMPLAINT,
    OutboxStatus.DELIVERED,
    OutboxStatus.FAILED_PERMANENT,
}
LEASABLE_STATUSES = {OutboxStatus.QUEUED, OutboxStatus.FAILED_RETRYABLE, OutboxStatus.PROCESSING}


def _retry_delay(attempts: int) -> int:
    return min(3600, 30 * (2 ** max(0, attempts - 1))) + random.randint(0, 15)


def _lease_outbox(outbox_id: str) -> EmailOutbox | None:
    now = timezone.now()
    with transaction.atomic():
        outbox = EmailOutbox.objects.select_for_update().filter(pk=outbox_id).first()
        if outbox is None or outbox.delivery_mode != DeliveryMode.OPENPGP or outbox.status not in LEASABLE_STATUSES:
            return None
        if outbox.expires_at and outbox.expires_at <= now:
            outbox.status = OutboxStatus.FAILED_PERMANENT
            outbox.last_error_code = "message_expired"
            outbox.last_error_detail = "The delivery validity window expired"
            outbox.encrypted_message = b""
            outbox.terminal_at = now
            outbox.lease_expires_at = None
            outbox.save(
                update_fields=(
                    "status",
                    "last_error_code",
                    "last_error_detail",
                    "encrypted_message",
                    "terminal_at",
                    "lease_expires_at",
                    "updated_at",
                )
            )
            return None
        if outbox.status == OutboxStatus.PROCESSING and outbox.lease_expires_at and outbox.lease_expires_at > now:
            return None
        if outbox.next_attempt_at and outbox.next_attempt_at > now:
            return None
        outbox.status = OutboxStatus.PROCESSING
        outbox.attempts += 1
        outbox.lease_expires_at = now + LEASE_DURATION
        outbox.last_error_code = ""
        outbox.last_error_detail = ""
        outbox.save(
            update_fields=(
                "status",
                "attempts",
                "lease_expires_at",
                "last_error_code",
                "last_error_detail",
                "updated_at",
            )
        )
        return outbox


@shared_task
def deliver_email_outbox(outbox_id: str):
    if not settings.EMAIL_DELIVERY_V2_ENABLED:
        return
    outbox = _lease_outbox(outbox_id)
    if outbox is None:
        return

    try:
        message = render_outbox_message(outbox)
        receipt = get_transport(settings.EMAIL_PROVIDER).send(
            message,
            configuration_set=outbox.configuration_set,
            message_tags={"outbox_id": str(outbox.id), "mail_class": outbox.policy_class},
        )
    except MailAcceptanceUnknownError as exc:
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.ACCEPTANCE_UNKNOWN,
            lease_expires_at=None,
            next_attempt_at=None,
            last_error_code="acceptance_unknown",
            last_error_detail=str(exc)[:255],
        )
        return
    except MailRetryableError as exc:
        now = timezone.now()
        if outbox.attempts >= MAX_DELIVERY_ATTEMPTS or (outbox.expires_at and outbox.expires_at <= now):
            EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
                status=OutboxStatus.FAILED_PERMANENT,
                lease_expires_at=None,
                next_attempt_at=None,
                last_error_code="retry_exhausted",
                last_error_detail=str(exc)[:255],
                terminal_at=now,
                encrypted_message=b"",
            )
            return
        delay = _retry_delay(outbox.attempts)
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.FAILED_RETRYABLE,
            lease_expires_at=None,
            next_attempt_at=now + timedelta(seconds=delay),
            last_error_code="smtp_retryable",
            last_error_detail=str(exc)[:255],
        )
        try:
            deliver_email_outbox.apply_async(args=(str(outbox.id),), countdown=delay)
        except Exception:
            logger.exception("Could not publish email retry; the due-outbox dispatcher will recover it")
        return
    except MailPermanentError as exc:
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.FAILED_PERMANENT,
            lease_expires_at=None,
            next_attempt_at=None,
            last_error_code="smtp_permanent",
            last_error_detail=str(exc)[:255],
            terminal_at=timezone.now(),
            encrypted_message=b"",
        )
        return
    except Exception as exc:
        logger.exception(
            "Unexpected outbound email failure",
            extra={"outbox_id": str(outbox.id), "error_type": type(exc).__name__},
        )
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.FAILED_PERMANENT,
            lease_expires_at=None,
            next_attempt_at=None,
            last_error_code=type(exc).__name__[:64],
            last_error_detail="Delivery failed safely; inspect typed worker logs",
            terminal_at=timezone.now(),
            encrypted_message=b"",
        )
        return

    updated = EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
        status=OutboxStatus.ACCEPTED,
        accepted_at=timezone.now(),
        lease_expires_at=None,
        next_attempt_at=None,
        provider_message_id=receipt.provider_message_id,
        last_error_code="",
        last_error_detail="",
    )
    if updated:
        EmailNotificationLog.objects.filter(outbox_id=outbox.id, sent_at__isnull=True).update(sent_at=timezone.now())


@shared_task
def recover_stale_email_outbox():
    if not settings.EMAIL_DELIVERY_V2_ENABLED:
        return
    now = timezone.now()
    EmailOutbox.objects.filter(
        delivery_mode=DeliveryMode.CLEAR,
        status=OutboxStatus.PROCESSING,
        lease_expires_at__lte=now,
    ).update(
        status=OutboxStatus.ACCEPTANCE_UNKNOWN,
        lease_expires_at=None,
        next_attempt_at=None,
        last_error_code="clear_delivery_interrupted",
        last_error_detail="Clear account delivery was interrupted and will not be retried",
    )
    stale_ids = list(
        EmailOutbox.objects.filter(
            delivery_mode=DeliveryMode.OPENPGP,
            status=OutboxStatus.PROCESSING,
            lease_expires_at__lte=now,
        ).values_list("id", flat=True)[:500]
    )
    EmailOutbox.objects.filter(id__in=stale_ids).update(
        status=OutboxStatus.FAILED_RETRYABLE,
        lease_expires_at=None,
        next_attempt_at=now,
        last_error_code="stale_lease",
        last_error_detail="A worker lease expired before completion",
    )
    for outbox_id in stale_ids:
        try:
            deliver_email_outbox.delay(str(outbox_id))
        except Exception:
            logger.exception("Could not republish a recovered email outbox row", extra={"outbox_id": str(outbox_id)})


@shared_task
def dispatch_due_email_outbox():
    """Republish due rows so broker publication is never a single point of failure."""

    if not settings.EMAIL_DELIVERY_V2_ENABLED:
        return
    now = timezone.now()
    due_ids = list(
        EmailOutbox.objects.filter(
            delivery_mode=DeliveryMode.OPENPGP,
            status__in=[OutboxStatus.QUEUED, OutboxStatus.FAILED_RETRYABLE],
            next_attempt_at__lte=now,
        )
        .order_by("next_attempt_at")
        .values_list("id", flat=True)[:500]
    )
    for outbox_id in due_ids:
        try:
            deliver_email_outbox.delay(str(outbox_id))
        except Exception:
            logger.exception("Could not publish a due email outbox row", extra={"outbox_id": str(outbox_id)})
            break


@shared_task
def expire_openpgp_keys():
    now = timezone.now()
    UserOpenPGPKey.objects.filter(
        status__in=[OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.PENDING, OpenPGPKeyStatus.REPLACED],
        key_expires_at__isnull=False,
        key_expires_at__lte=now,
    ).update(status=OpenPGPKeyStatus.EXPIRED, updated_at=now)


def _sqs_client():
    kwargs = {"region_name": settings.EMAIL_SES_REGION}
    if settings.EMAIL_EVENTS_AWS_ACCESS_KEY_ID:
        kwargs.update(
            {
                "aws_access_key_id": settings.EMAIL_EVENTS_AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": settings.EMAIL_EVENTS_AWS_SECRET_ACCESS_KEY,
                "aws_session_token": settings.EMAIL_EVENTS_AWS_SESSION_TOKEN or None,
            }
        )
    return boto3.client("sqs", **kwargs)


def _event_timestamp(event: dict):
    event_type = str(event.get("eventType") or event.get("notificationType") or "").lower()
    detail_key = "deliveryDelay" if event_type == "deliverydelay" else event_type
    detail = event.get(detail_key, {})
    candidate = detail.get("timestamp") if isinstance(detail, dict) else None
    candidate = candidate or event.get("mail", {}).get("timestamp")
    parsed = parse_datetime(candidate) if isinstance(candidate, str) else None
    return parsed or timezone.now()


def _outbox_from_event(event: dict) -> EmailOutbox | None:
    tags = event.get("mail", {}).get("tags", {})
    values = tags.get("outbox_id", []) if isinstance(tags, dict) else []
    if not isinstance(values, list) or len(values) != 1:
        return None
    try:
        outbox_id = uuid.UUID(values[0])
    except (ValueError, TypeError, AttributeError):
        return None
    return EmailOutbox.objects.filter(pk=outbox_id).first()


def _minimal_event_metadata(event_type: str, event: dict) -> dict:
    if event_type == "bounce":
        return {"bounce_type": str(event.get("bounce", {}).get("bounceType", ""))[:32]}
    if event_type == "complaint":
        return {"feedback_type": str(event.get("complaint", {}).get("complaintFeedbackType", ""))[:32]}
    if event_type == "delivery":
        return {"processing_time_ms": event.get("delivery", {}).get("processingTimeMillis")}
    if event_type == "deliverydelay":
        return {"delay_type": str(event.get("deliveryDelay", {}).get("delayType", ""))[:32]}
    return {}


def process_ses_event(raw_message: str) -> None:
    if len(raw_message.encode("utf-8")) > 256 * 1024:
        raise ValueError("SES event exceeds the maximum accepted size")
    envelope = json.loads(raw_message)
    if not isinstance(envelope, dict):
        raise ValueError("SNS envelope must be an object")
    if settings.EMAIL_SES_EVENTS_TOPIC_ARN and envelope.get("TopicArn") != settings.EMAIL_SES_EVENTS_TOPIC_ARN:
        raise ValueError("SNS topic does not match the configured SES event topic")
    message = envelope.get("Message")
    event = json.loads(message) if isinstance(message, str) else envelope
    if not isinstance(event, dict):
        raise ValueError("SES event must be an object")

    mail = event.get("mail")
    if not isinstance(mail, dict):
        raise ValueError("SES event has no mail metadata")
    if settings.EMAIL_SES_ACCOUNT_ID and str(mail.get("sendingAccountId")) != settings.EMAIL_SES_ACCOUNT_ID:
        raise ValueError("SES event account does not match the configured account")

    event_type = str(event.get("eventType") or event.get("notificationType") or "").lower()
    allowed = {"send", "delivery", "bounce", "complaint", "reject", "renderingfailure", "deliverydelay"}
    if event_type not in allowed:
        raise ValueError("SES event type is not allowlisted")
    outbox = _outbox_from_event(event)
    provider_message_id = str(mail.get("messageId", ""))[:255]
    occurred_at = _event_timestamp(event)
    metadata = _minimal_event_metadata(event_type, event)
    event_identity = json.dumps(
        {
            "event_type": event_type,
            "metadata": metadata,
            "occurred_at": occurred_at.isoformat(),
            "provider_message_id": provider_message_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    provider_event_id = hashlib.sha256(event_identity.encode("utf-8")).hexdigest()

    with transaction.atomic():
        delivery_event, created = EmailDeliveryEvent.objects.get_or_create(
            provider_event_id=provider_event_id,
            defaults={
                "outbox": outbox,
                "provider_message_id": provider_message_id,
                "event_type": event_type,
                "occurred_at": occurred_at,
                "metadata": metadata,
            },
        )
        if not created or outbox is None:
            return
        outbox = EmailOutbox.objects.select_for_update().get(pk=outbox.id)
        if outbox.provider_message_id and provider_message_id and outbox.provider_message_id != provider_message_id:
            raise ValueError("SES event message identifier does not match the outbox receipt")
        if outbox.provider_events.exclude(pk=delivery_event.pk).filter(occurred_at__gt=occurred_at).exists():
            return
        now = timezone.now()
        if event_type == "send":
            EmailOutbox.objects.filter(pk=outbox.id).exclude(status__in=TERMINAL_STATUSES).update(
                status=OutboxStatus.ACCEPTED,
                accepted_at=outbox.accepted_at or now,
                provider_message_id=provider_message_id,
                last_error_code="",
                last_error_detail="",
            )
            EmailNotificationLog.objects.filter(outbox_id=outbox.id, sent_at__isnull=True).update(sent_at=now)
        elif event_type == "delivery":
            updated = (
                EmailOutbox.objects.filter(pk=outbox.id)
                .exclude(status__in=TERMINAL_STATUSES)
                .update(
                    status=OutboxStatus.DELIVERED,
                    delivered_at=now,
                    terminal_at=now,
                    provider_message_id=provider_message_id,
                    encrypted_message=b"",
                )
            )
            if updated:
                EmailNotificationLog.objects.filter(outbox_id=outbox.id, sent_at__isnull=True).update(sent_at=now)
        elif event_type == "complaint" or (
            event_type == "bounce" and str(event.get("bounce", {}).get("bounceType", "")).lower() == "permanent"
        ):
            reason = SuppressionReason.HARD_BOUNCE if event_type == "bounce" else SuppressionReason.COMPLAINT
            EmailSuppression.objects.get_or_create(
                email_address=outbox.recipient_email,
                reason=reason,
                is_active=True,
                defaults={
                    "recipient": outbox.recipient,
                    "source": "ses",
                    "provider_event_id": delivery_event.provider_event_id,
                },
            )
            EmailOutbox.objects.filter(pk=outbox.id).update(
                status=OutboxStatus.FAILED_PERMANENT,
                terminal_at=now,
                provider_message_id=provider_message_id,
                last_error_code=f"ses_{event_type}",
                last_error_detail="SES reported a terminal recipient event",
                encrypted_message=b"",
            )
        elif event_type == "bounce":
            EmailOutbox.objects.filter(pk=outbox.id).update(
                last_error_code="ses_transient_bounce",
                last_error_detail="SES reported a non-permanent bounce; the recipient was not suppressed",
                provider_message_id=provider_message_id,
            )
        elif event_type in {"reject", "renderingfailure"}:
            EmailOutbox.objects.filter(pk=outbox.id).update(
                status=OutboxStatus.FAILED_PERMANENT,
                terminal_at=now,
                provider_message_id=provider_message_id,
                last_error_code=f"ses_{event_type}",
                last_error_detail="SES reported a terminal delivery event",
                encrypted_message=b"",
            )
        elif event_type == "deliverydelay":
            EmailOutbox.objects.filter(pk=outbox.id).update(
                provider_message_id=provider_message_id,
                last_error_code="ses_delivery_delay",
                last_error_detail="SES reported delayed delivery",
            )


@shared_task
def consume_ses_email_events():
    if not settings.EMAIL_DELIVERY_V2_ENABLED or not settings.EMAIL_SES_EVENTS_QUEUE_URL:
        return
    client = _sqs_client()
    deadline = time.monotonic() + 45
    batches = 0
    while batches < 50 and time.monotonic() < deadline:
        response = client.receive_message(
            QueueUrl=settings.EMAIL_SES_EVENTS_QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=2,
            VisibilityTimeout=120,
            AttributeNames=["ApproximateReceiveCount"],
        )
        messages = response.get("Messages", [])
        if not messages:
            break
        batches += 1
        for message in messages:
            receipt_handle = message.get("ReceiptHandle")
            body = message.get("Body")
            if not receipt_handle or not isinstance(body, str):
                continue
            try:
                process_ses_event(body)
            except (ValueError, json.JSONDecodeError):
                logger.warning(
                    "Rejected invalid SES event",
                    extra={
                        "sqs_message_id": message.get("MessageId", ""),
                        "receive_count": message.get("Attributes", {}).get("ApproximateReceiveCount", ""),
                    },
                )
                continue
            client.delete_message(QueueUrl=settings.EMAIL_SES_EVENTS_QUEUE_URL, ReceiptHandle=receipt_handle)


@shared_task
def cleanup_secure_email_records():
    now = timezone.now()
    outbox_cutoff = now - timedelta(days=settings.EMAIL_OUTBOX_RETENTION_DAYS)
    audit_cutoff = now - timedelta(days=settings.EMAIL_AUDIT_RETENTION_DAYS)
    event_cutoff = now - timedelta(days=settings.EMAIL_EVENT_RETENTION_DAYS)
    EmailDeliveryEvent.all_objects.filter(created_at__lte=event_cutoff).delete()
    EmailOutbox.all_objects.filter(terminal_at__lte=audit_cutoff).delete()
    # Provider feedback is best-effort: SES can accept a message without ever
    # producing a terminal delivery event, and an ambiguous API response can
    # remain in acceptance_unknown forever.  Bound those audit-only rows by
    # their creation time so the configured retention window is still real.
    EmailOutbox.all_objects.filter(
        status__in=[OutboxStatus.ACCEPTED, OutboxStatus.ACCEPTANCE_UNKNOWN],
        created_at__lte=audit_cutoff,
    ).delete()
    EmailOutbox.all_objects.filter(
        status__in=[OutboxStatus.ACCEPTED, OutboxStatus.ACCEPTANCE_UNKNOWN],
        created_at__lte=outbox_cutoff,
    ).exclude(encrypted_message=b"").update(encrypted_message=b"", updated_at=now)
    OpenPGPKeyChallenge.all_objects.filter(expires_at__lte=now - timedelta(days=1)).delete()
    UserOpenPGPKey.all_objects.filter(
        status__in=[
            OpenPGPKeyStatus.EXPIRED,
            OpenPGPKeyStatus.INVALID,
            OpenPGPKeyStatus.REPLACED,
            OpenPGPKeyStatus.REVOKED,
        ],
        updated_at__lte=outbox_cutoff,
        outbox_entries__isnull=True,
    ).delete()
