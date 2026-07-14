"""Public enqueue API and message rendering for outbound email."""

import base64
import json
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from email.utils import parseaddr
from functools import partial

from django.conf import settings
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from plane.db.models import EmailOutbox, EmailSuppression, UserOpenPGPKey
from plane.license.utils.instance_value import get_email_configuration

from .crypto import decrypt_bytes, email_receipt_code, encrypt_bytes, encrypt_json, keyed_digest
from .enums import DeliveryMode, MailDecision, OpenPGPKeyStatus, OutboxStatus, SuppressionReason
from .exceptions import MailPolicyError
from .mime import build_clear_message, build_encrypted_message, sanitize_email_html
from .policy import resolve_mail_policy
from .registry import get_template_definition
from .transports import get_transport


@dataclass(frozen=True)
class EnqueueResult:
    outbox_id: uuid.UUID | None
    status: str


def _normalized_email(email: str) -> str:
    normalized = email.strip().lower()
    validate_email(normalized)
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
    plaintext = decrypt_bytes(
        key.certificate_ciphertext,
        associated_data=f"openpgp-certificate:{key.id}".encode(),
    )
    return plaintext.decode("utf-8")


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
    if outbox.payload_schema_version != 1:
        raise MailPolicyError("The secure email payload schema is not supported")
    if not outbox.payload_ciphertext:
        raise MailPolicyError("The secure email payload is unavailable")
    definition = get_template_definition(outbox.template_key)
    key = None
    if outbox.openpgp_key_id:
        key = outbox.openpgp_key
        permitted_statuses = {OpenPGPKeyStatus.ACTIVE, OpenPGPKeyStatus.REPLACED}
        if outbox.template_key in {"security.openpgp_challenge", "security.openpgp_test"}:
            permitted_statuses.add(OpenPGPKeyStatus.PENDING)
        if key is None or key.status not in permitted_statuses:
            raise MailPolicyError("The selected OpenPGP key is no longer usable")
        if key.key_expires_at is not None and key.key_expires_at <= timezone.now():
            UserOpenPGPKey.objects.filter(pk=key.id).update(status=OpenPGPKeyStatus.EXPIRED)
            raise MailPolicyError("The selected OpenPGP key has expired")
    elif settings.EMAIL_OPENPGP_ENABLED:
        current_policy = resolve_mail_policy(
            definition.policy_class,
            has_active_key=False,
            openpgp_enabled=True,
        )
        if current_policy.decision == MailDecision.SUPPRESS:
            raise MailPolicyError("Current policy no longer permits cleartext delivery")

    payload = json.loads(
        decrypt_bytes(
            outbox.payload_ciphertext,
            associated_data=f"email-outbox-payload:{outbox.id}".encode(),
        )
    )
    recipient = decrypt_bytes(
        outbox.recipient_email_ciphertext,
        associated_data=f"email-outbox-recipient:{outbox.id}".encode(),
    ).decode("utf-8")
    sender = outbox.sender
    attachments = [
        {
            "filename": item["filename"],
            "content_type": item["content_type"],
            "content": base64.b64decode(item["content_base64"], validate=True),
        }
        for item in payload.get("attachments", [])
    ]
    if key is not None:
        return build_encrypted_message(
            inner_subject=payload["subject"],
            text_body=payload["text_body"],
            html_body=payload.get("html_body", ""),
            sender=sender,
            recipient=recipient,
            message_id=outbox.message_id,
            certificate=_certificate_for_key(key),
            encryption_subkey_fingerprint=outbox.openpgp_fingerprint,
            reply_to=payload.get("reply_to", ""),
            receipt_code=outbox.receipt_code,
            attachments=attachments,
        )
    return build_clear_message(
        subject=payload["subject"],
        text_body=payload["text_body"],
        html_body=payload.get("html_body", ""),
        sender=sender,
        recipient=recipient,
        message_id=outbox.message_id,
        reply_to=payload.get("reply_to", ""),
        include_security_notice=definition.include_security_notice,
        receipt_code=outbox.receipt_code,
        attachments=attachments,
    )


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
    """Validate policy and create a durable, encrypted outbox item."""

    definition = get_template_definition(template_key)
    recipient_email = _normalized_email(recipient_email)
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
    serialized_attachments = []
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
        serialized_attachments.append(
            {
                "filename": filename,
                "content_type": content_type,
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        )
    if total_attachment_bytes > settings.EMAIL_MAX_ATTACHMENT_BYTES:
        raise MailPolicyError("Email attachments exceed the configured size limit")
    if len(text_body.encode("utf-8")) + len(html_body.encode("utf-8")) > settings.EMAIL_MAX_STORED_PAYLOAD_BYTES:
        raise MailPolicyError("The rendered email exceeds the secure outbox size limit")
    html_body = sanitize_email_html(html_body)

    # Preserve the existing SMTP behavior until an operator explicitly enables
    # durable delivery.  This path deliberately has no OpenPGP, audit receipt,
    # or outbox guarantees and therefore does not require the new crypto keys.
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
            attachments=[
                {
                    "filename": item["filename"],
                    "content_type": item["content_type"],
                    "content": base64.b64decode(item["content_base64"], validate=True),
                }
                for item in serialized_attachments
            ],
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

    outbox_id = uuid.uuid4()
    email_hash = keyed_digest(recipient_email, purpose="recipient-email")
    suppression = EmailSuppression.objects.filter(email_hash=email_hash, is_active=True).order_by("-created_at").first()
    status = OutboxStatus.QUEUED
    if suppression:
        status = (
            OutboxStatus.SUPPRESSED_COMPLAINT
            if suppression.reason == SuppressionReason.COMPLAINT
            else OutboxStatus.SUPPRESSED_BOUNCE
        )
    elif policy.decision == MailDecision.SUPPRESS:
        status = OutboxStatus.SUPPRESSED_NO_KEY

    payload = {
        "subject": subject,
        "text_body": text_body,
        "html_body": html_body,
        "reply_to": reply_to,
        "attachments": serialized_attachments,
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    intent_digest = keyed_digest(
        f"{recipient_email}\0{template_key}\0{base64.b64encode(serialized).decode('ascii')}",
        purpose="email-intent",
    )
    if status == OutboxStatus.QUEUED and len(serialized) > settings.EMAIL_MAX_STORED_PAYLOAD_BYTES:
        raise MailPolicyError("The rendered email exceeds the secure outbox size limit")

    now = timezone.now()
    sender = _configured_sender()
    delivery_mode = DeliveryMode.CLEAR
    if policy.decision == MailDecision.ENCRYPT:
        delivery_mode = DeliveryMode.OPENPGP
    elif status != OutboxStatus.QUEUED:
        delivery_mode = DeliveryMode.SUPPRESSED
    defaults = {
        "id": outbox_id,
        "recipient": recipient_user,
        "recipient_email_ciphertext": encrypt_bytes(
            recipient_email.encode(),
            associated_data=f"email-outbox-recipient:{outbox_id}".encode(),
        ),
        "recipient_email_hash": email_hash,
        "policy_class": definition.policy_class,
        "template_key": template_key,
        "audit_label": definition.audit_label,
        "sender": sender,
        "delivery_mode": delivery_mode,
        "payload_ciphertext": (
            encrypt_json(payload, associated_data=f"email-outbox-payload:{outbox_id}".encode())
            if status == OutboxStatus.QUEUED
            else ""
        ),
        "intent_digest": intent_digest,
        "message_id": f"<{outbox_id}@{settings.EMAIL_MESSAGE_ID_DOMAIN}>",
        "receipt_code": email_receipt_code(outbox_id),
        "openpgp_key": active_key if policy.decision == MailDecision.ENCRYPT else None,
        "openpgp_fingerprint": active_key.encryption_subkey_fingerprint
        if policy.decision == MailDecision.ENCRYPT and active_key
        else "",
        "configuration_set": _configuration_set(definition.configuration_set_kind),
        "status": status,
        "next_attempt_at": now if status == OutboxStatus.QUEUED else None,
        "expires_at": now + expires_in if expires_in else None,
        "suppressed_at": now if status != OutboxStatus.QUEUED else None,
        "terminal_at": now if status != OutboxStatus.QUEUED else None,
    }
    with transaction.atomic():
        outbox, created = EmailOutbox.objects.get_or_create(
            idempotency_key=idempotency_key or f"ad-hoc:{outbox_id}",
            defaults=defaults,
        )
        if not created and (
            outbox.recipient_email_hash != email_hash
            or outbox.template_key != template_key
            or outbox.policy_class != definition.policy_class
            or outbox.intent_digest != intent_digest
        ):
            raise MailPolicyError("The idempotency key was already used for a different email intent")
        if created and status == OutboxStatus.QUEUED:
            from plane.bgtasks.email_delivery_task import deliver_email_outbox

            transaction.on_commit(partial(deliver_email_outbox.delay, str(outbox.id)))
    return EnqueueResult(outbox.id, outbox.status)


def render_outbox_message(outbox: EmailOutbox):
    """Render an already-authorized outbox item for its selected key version."""

    return _render_message(outbox)
