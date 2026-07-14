# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Privacy-minimized email receipt representations."""

from plane.db.models import EmailOutbox
from plane.mailer.crypto import decrypt_bytes


def email_receipt(outbox: EmailOutbox, *, admin: bool = False) -> dict:
    data = {
        "receipt_code": outbox.receipt_code,
        "message_id": outbox.message_id,
        "mail_type": outbox.audit_label,
        "sender": outbox.sender,
        "delivery_mode": outbox.delivery_mode,
        "status": outbox.status,
        "created_at": outbox.created_at,
        "accepted_at": outbox.accepted_at,
        "delivered_at": outbox.delivered_at,
        "key_fingerprint": outbox.openpgp_fingerprint or None,
    }
    if admin:
        try:
            recipient_email = decrypt_bytes(
                outbox.recipient_email_ciphertext,
                associated_data=f"email-outbox-recipient:{outbox.id}".encode(),
            ).decode("utf-8")
        except Exception:
            recipient_email = None
        data.update(
            {
                "id": outbox.id,
                "recipient_user_id": outbox.recipient_id,
                "recipient_email_hash": outbox.recipient_email_hash,
                "recipient_email": recipient_email,
                "template_key": outbox.template_key,
                "policy_class": outbox.policy_class,
                "configuration_set": outbox.configuration_set,
                "provider_message_id": outbox.provider_message_id or None,
                "attempts": outbox.attempts,
                "last_error_code": outbox.last_error_code or None,
            }
        )
    return data
