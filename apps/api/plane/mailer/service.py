# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public enqueue API and message rendering for outbound email."""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from email import policy as email_policy
from email.parser import BytesParser
from email.utils import parseaddr
from functools import partial

from django.conf import settings
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from plane.db.models import EmailOutbox, EmailSuppression, UserOpenPGPKey
from plane.license.utils.instance_value import get_email_configuration

from .enums import DeliveryMode, MailDecision, OpenPGPKeyStatus, OutboxStatus, SuppressionReason
from .exceptions import MailAcceptanceUnknownError, MailPolicyError, MailerError
from .mime import build_clear_message, build_encrypted_message, sanitize_email_html
from .policy import resolve_mail_policy
from .registry import MailTemplateDefinition, get_template_definition
from .tokens import email_receipt_code
from .transports import get_transport

logger = logging.getLogger("plane.worker")


@dataclass(frozen=True)
class EnqueueResult:
    outbox_id: uuid.UUID | None
    status: str


def _normalized_email(email: str) -> str:
    if not isinstance(email, str):
        raise MailPolicyError("The recipient email address is invalid")
    normalized = email.strip().lower()
    try:
        validate_email(normalized)
    except Exception as exc:
        raise MailPolicyError("The recipient email address is invalid") from exc
    return normalized


def _active_key_for_user(user) -> UserOpenPGPKey | None:
    if user is None:
        return None
    now = timezone.now()
    return (
        UserOpenPGPKey.objects.filter(user=user, status=OpenPGPKeyStatus.ACTIVE)
        .filter(key_expires_at__isnull=True)
        .first()
        or UserOpenPGPKey.objects.filter(
            user=user,
            status=OpenPGPKeyStatus.ACTIVE,
            key_expires_at__gt=now,
        ).first()
    )


def _configuration_set(kind: str) -> str:
    if kind == "auth":
        return settings.EMAIL_SES_CONFIGURATION_SET_AUTH
    return settings.EMAIL_SES_CONFIGURATION_SET_NOTIFICATIONS


def _certificate_for_key(key: UserOpenPGPKey) -> str:
    return key.certificate


def _configured_sender() -> str:
    _host, _user, _password, _port, _tls, _ssl, sender = get_email_configuration()
    if not sender or any(character in sender for character in "\r\n"):
        raise MailPolicyError("The configured sender address is invalid")
    _display_name, address = parseaddr(sender)
    try:
        validate_email(address)
    except Exception as exc:
        raise MailPolicyError("The configured sender address is invalid") from exc
    return sender


def _render_message(outbox: EmailOutbox):
    if outbox.delivery_mode != DeliveryMode.OPENPGP or not outbox.encrypted_message:
        raise MailPolicyError("The OpenPGP outbox message is unavailable")
    key = outbox.openpgp_key
    permitted_statuses = {OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.REPLACED}
    if outbox.template_key in {"security.openpgp_challenge", "security.openpgp_test"}:
        permitted_statuses.add(OpenPGPKeyStatus.PENDING)
    if key is None or key.status not in permitted_statuses:
        raise MailPolicyError("The selected OpenPGP key is no longer usable")
    if key.key_expires_at is not None and key.key_expires_at <= timezone.now():
        UserOpenPGPKey.objects.filter(pk=key.id).update(status=OpenPGPKeyStatus.EXPIRED)
        raise MailPolicyError("The selected OpenPGP key has expired")
    try:
        message = BytesParser(policy=email_policy.SMTP).parsebytes(bytes(outbox.encrypted_message))
    except (TypeError, ValueError) as exc:
        raise MailPolicyError("The stored OpenPGP message is malformed") from exc
    if (
        message.defects
        or message.get_content_type() != "multipart/encrypted"
        or message.get_param("protocol") != "application/pgp-encrypted"
        or str(message.get("Subject", "")) != "Encrypted Hangar notification"
        or str(message.get("From", "")) != outbox.sender
        or str(message.get("To", "")).lower() != outbox.recipient_email
        or str(message.get("Message-ID", "")) != outbox.message_id
    ):
        raise MailPolicyError("The stored OpenPGP message failed integrity validation")
    return message


def _same_idempotent_intent(
    outbox: EmailOutbox,
    *,
    recipient_email: str,
    recipient_user: object | None,
    template_key: str,
    definition: MailTemplateDefinition,
) -> bool:
    return (
        outbox.recipient_email == recipient_email
        and outbox.recipient_id == getattr(recipient_user, "id", None)
        and outbox.template_key == template_key
        and outbox.policy_class == definition.policy_class
    )


def _send_clear_message(outbox: EmailOutbox, message) -> EnqueueResult:
    """Submit clear account mail once without placing its content in durable storage."""

    try:
        receipt = get_transport(settings.EMAIL_PROVIDER).send(
            message,
            configuration_set=outbox.configuration_set,
            message_tags={"outbox_id": str(outbox.id), "mail_class": outbox.policy_class},
        )
    except MailAcceptanceUnknownError:
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.ACCEPTANCE_UNKNOWN,
            lease_expires_at=None,
            last_error_code="acceptance_unknown",
            last_error_detail="The provider response was lost; clear account mail will not be retried",
        )
    except MailerError as exc:
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.FAILED_PERMANENT,
            lease_expires_at=None,
            terminal_at=timezone.now(),
            last_error_code=type(exc).__name__[:64],
            last_error_detail="Clear account mail failed before confirmed acceptance and will not be retried",
        )
    except Exception as exc:
        logger.exception(
            "Unexpected clear account email failure",
            extra={"outbox_id": str(outbox.id), "error_type": type(exc).__name__},
        )
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.FAILED_PERMANENT,
            lease_expires_at=None,
            terminal_at=timezone.now(),
            last_error_code=type(exc).__name__[:64],
            last_error_detail="Clear account mail failed safely; inspect typed worker logs",
        )
    else:
        EmailOutbox.objects.filter(pk=outbox.id, status=OutboxStatus.PROCESSING).update(
            status=OutboxStatus.ACCEPTED,
            lease_expires_at=None,
            accepted_at=timezone.now(),
            provider_message_id=receipt.provider_message_id,
            last_error_code="",
            last_error_detail="",
        )
    outbox.refresh_from_db()
    return EnqueueResult(outbox.id, outbox.status)


def enqueue_rendered_email(
    *,
    recipient_email: str,
    template_key: str,
    subject: str,
    text_body: str,
    html_body: str = "",
    recipient_user=None,
    idempotency_key: str | None = None,
    expires_in: timedelta | None = None,
    reply_to: str = "",
    encryption_key: UserOpenPGPKey | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> EnqueueResult:
    """Apply mail policy and persist only encrypted notification content."""

    definition = get_template_definition(template_key)
    recipient_email = _normalized_email(recipient_email)
    if idempotency_key is not None and (
        not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 255
    ):
        raise MailPolicyError("The email idempotency key is invalid")
    if expires_in is not None and (not isinstance(expires_in, timedelta) or expires_in <= timedelta(0)):
        raise MailPolicyError("The email expiry window is invalid")
    if recipient_user is not None and _normalized_email(recipient_user.email) != recipient_email:
        raise MailPolicyError("The recipient user does not own the recipient email address")
    if encryption_key is not None and template_key not in {"security.openpgp_challenge", "security.openpgp_test"}:
        raise MailPolicyError("A producer cannot override the encryption key for this template")
    if not isinstance(subject, str) or not subject or len(subject) > 998 or any(c in subject for c in "\r\n"):
        raise MailPolicyError("The email subject is invalid")
    if not isinstance(text_body, str) or not isinstance(html_body, str):
        raise MailPolicyError("Email bodies must be text")
    reply_to = reply_to or settings.EMAIL_REPLY_TO
    if reply_to:
        if any(character in reply_to for character in "\r\n"):
            raise MailPolicyError("The reply-to address is invalid")
        _reply_name, reply_address = parseaddr(reply_to)
        try:
            validate_email(reply_address)
        except Exception as exc:
            raise MailPolicyError("The reply-to address is invalid") from exc
    validated_attachments = []
    total_attachment_bytes = 0
    if len(attachments or []) > 20:
        raise MailPolicyError("An email cannot contain more than 20 attachments")
    for filename, content, content_type in attachments or []:
        if not isinstance(content, bytes):
            raise MailPolicyError("Email attachments must be bytes")
        if (
            not isinstance(filename, str)
            or not filename
            or len(filename) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        ):
            raise MailPolicyError("An email attachment filename is invalid")
        if not isinstance(content_type, str) or not re.fullmatch(
            r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", content_type
        ):
            raise MailPolicyError("An email attachment content type is invalid")
        total_attachment_bytes += len(content)
        validated_attachments.append(
            {
                "filename": filename,
                "content_type": content_type,
                "content": content,
            }
        )
    if total_attachment_bytes > settings.EMAIL_MAX_ATTACHMENT_BYTES:
        raise MailPolicyError("Email attachments exceed the configured size limit")
    if len(text_body.encode("utf-8")) + len(html_body.encode("utf-8")) > settings.EMAIL_MAX_STORED_PAYLOAD_BYTES:
        raise MailPolicyError("The rendered email exceeds the secure outbox size limit")
    html_body = sanitize_email_html(html_body)

    # Preserve the existing SMTP behavior until an operator explicitly enables
    # policy-aware delivery. This path has no OpenPGP or audit receipt.
    if not settings.EMAIL_DELIVERY_V2_ENABLED:
        if encryption_key is not None:
            raise MailPolicyError("OpenPGP email requires durable delivery")
        message_id = f"<{uuid.uuid4()}@{settings.EMAIL_MESSAGE_ID_DOMAIN}>"
        message = build_clear_message(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            sender=_configured_sender(),
            recipient=recipient_email,
            message_id=message_id,
            reply_to=reply_to,
            include_security_notice=False,
            attachments=validated_attachments,
        )
        get_transport(settings.EMAIL_PROVIDER).send(
            message,
            configuration_set=_configuration_set(definition.configuration_set_kind),
        )
        return EnqueueResult(None, OutboxStatus.ACCEPTED)

    active_key = encryption_key or _active_key_for_user(recipient_user)
    policy = resolve_mail_policy(
        definition.policy_class,
        has_active_key=active_key is not None,
        openpgp_enabled=settings.EMAIL_OPENPGP_ENABLED or encryption_key is not None,
    )

    suppression = (
        EmailSuppression.objects.filter(email_address=recipient_email, is_active=True).order_by("-created_at").first()
    )
    delivery_mode = DeliveryMode.OPENPGP if policy.decision == MailDecision.ENCRYPT else DeliveryMode.CLEAR
    status = OutboxStatus.QUEUED if delivery_mode == DeliveryMode.OPENPGP else OutboxStatus.PROCESSING
    if suppression:
        status = (
            OutboxStatus.SUPPRESSED_COMPLAINT
            if suppression.reason == SuppressionReason.COMPLAINT
            else OutboxStatus.SUPPRESSED_BOUNCE
        )
        delivery_mode = DeliveryMode.SUPPRESSED
    elif policy.decision == MailDecision.SUPPRESS:
        status = OutboxStatus.SUPPRESSED_NO_KEY
        delivery_mode = DeliveryMode.SUPPRESSED

    idempotency_value = idempotency_key or f"ad-hoc:{uuid.uuid4()}"
    existing = EmailOutbox.objects.filter(idempotency_key=idempotency_value).first()
    if existing is not None:
        if not _same_idempotent_intent(
            existing,
            recipient_email=recipient_email,
            recipient_user=recipient_user,
            template_key=template_key,
            definition=definition,
        ):
            raise MailPolicyError("The idempotency key was already used for a different email intent")
        return EnqueueResult(existing.id, existing.status)

    outbox_id = uuid.uuid4()
    now = timezone.now()
    sender = _configured_sender()
    message_id = f"<{outbox_id}@{settings.EMAIL_MESSAGE_ID_DOMAIN}>"
    receipt_code = email_receipt_code()
    clear_message = None
    encrypted_message = b""
    if delivery_mode == DeliveryMode.OPENPGP:
        if active_key is None:
            raise MailPolicyError("The selected OpenPGP key is unavailable")
        message = build_encrypted_message(
            inner_subject=subject,
            text_body=text_body,
            html_body=html_body,
            sender=sender,
            recipient=recipient_email,
            message_id=message_id,
            certificate=_certificate_for_key(active_key),
            encryption_subkey_fingerprint=active_key.encryption_subkey_fingerprint,
            reply_to=reply_to,
            receipt_code=receipt_code,
            attachments=validated_attachments,
        )
        encrypted_message = message.as_bytes(policy=email_policy.SMTP)
        if len(encrypted_message) > settings.EMAIL_MAX_STORED_PAYLOAD_BYTES:
            raise MailPolicyError("The encrypted email exceeds the secure outbox size limit")
    elif delivery_mode == DeliveryMode.CLEAR:
        clear_message = build_clear_message(
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            sender=sender,
            recipient=recipient_email,
            message_id=message_id,
            reply_to=reply_to,
            include_security_notice=definition.include_security_notice,
            receipt_code=receipt_code,
            attachments=validated_attachments,
        )

    defaults = {
        "id": outbox_id,
        "recipient": recipient_user,
        "recipient_email": recipient_email,
        "policy_class": definition.policy_class,
        "template_key": template_key,
        "audit_label": definition.audit_label,
        "sender": sender,
        "delivery_mode": delivery_mode,
        "encrypted_message": encrypted_message,
        "message_id": message_id,
        "receipt_code": receipt_code,
        "openpgp_key": active_key if policy.decision == MailDecision.ENCRYPT else None,
        "openpgp_fingerprint": active_key.encryption_subkey_fingerprint
        if policy.decision == MailDecision.ENCRYPT and active_key
        else "",
        "configuration_set": _configuration_set(definition.configuration_set_kind),
        "status": status,
        "attempts": 1 if delivery_mode == DeliveryMode.CLEAR else 0,
        "next_attempt_at": now if delivery_mode == DeliveryMode.OPENPGP else None,
        "lease_expires_at": (
            now + timedelta(seconds=settings.EMAIL_SMTP_TIMEOUT_SECONDS + 30)
            if delivery_mode == DeliveryMode.CLEAR
            else None
        ),
        "expires_at": now + expires_in if expires_in else None,
        "suppressed_at": now if delivery_mode == DeliveryMode.SUPPRESSED else None,
        "terminal_at": now if delivery_mode == DeliveryMode.SUPPRESSED else None,
    }
    with transaction.atomic():
        outbox, created = EmailOutbox.objects.get_or_create(
            idempotency_key=idempotency_value,
            defaults=defaults,
        )
        if not created and not _same_idempotent_intent(
            outbox,
            recipient_email=recipient_email,
            recipient_user=recipient_user,
            template_key=template_key,
            definition=definition,
        ):
            raise MailPolicyError("The idempotency key was already used for a different email intent")
        if created and delivery_mode == DeliveryMode.OPENPGP:
            from plane.bgtasks.email_delivery_task import deliver_email_outbox

            transaction.on_commit(partial(deliver_email_outbox.delay, str(outbox.id)))
    if created and delivery_mode == DeliveryMode.CLEAR:
        if clear_message is None:
            raise MailPolicyError("The clear account message is unavailable")
        return _send_clear_message(outbox, clear_message)
    return EnqueueResult(outbox.id, outbox.status)


def render_outbox_message(outbox: EmailOutbox):
    """Load an already encrypted PGP/MIME message for delivery."""

    return _render_message(outbox)
