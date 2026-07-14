# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64

import pytest
from django.test import override_settings

from plane.mailer.crypto import decrypt_bytes, email_receipt_code, encrypt_bytes, keyed_digest
import uuid
from plane.mailer.exceptions import MailConfigurationError

KEY = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
LOOKUP_KEY = base64.urlsafe_b64encode(b"y" * 32).decode("ascii")


@pytest.mark.unit
@override_settings(EMAIL_OUTBOX_ENCRYPTION_KEYS=f"v1:{KEY}", EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
def test_authenticated_encryption_round_trip_and_random_nonce():
    first = encrypt_bytes(b"recipient@example.com", associated_data=b"outbox:1")
    second = encrypt_bytes(b"recipient@example.com", associated_data=b"outbox:1")

    assert first != second
    assert decrypt_bytes(first, associated_data=b"outbox:1") == b"recipient@example.com"


@pytest.mark.unit
@override_settings(EMAIL_OUTBOX_ENCRYPTION_KEYS=f"v1:{KEY}", EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
def test_ciphertext_cannot_be_moved_between_records():
    ciphertext = encrypt_bytes(b"secret", associated_data=b"outbox:1")

    with pytest.raises(MailConfigurationError):
        decrypt_bytes(ciphertext, associated_data=b"outbox:2")


@pytest.mark.unit
@override_settings(EMAIL_OUTBOX_ENCRYPTION_KEYS=f"v1:{KEY}", EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
def test_lookup_digest_is_stable_and_does_not_reveal_input():
    digest = keyed_digest("recipient@example.com", purpose="recipient-email")

    assert digest == keyed_digest("recipient@example.com", purpose="recipient-email")
    assert "recipient" not in digest
    assert digest != keyed_digest("recipient@example.com", purpose="another-purpose")


@pytest.mark.unit
@override_settings(EMAIL_OUTBOX_ENCRYPTION_KEYS=f"v1:{KEY}", EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
def test_email_receipt_is_stable_and_user_comparable():
    identifier = uuid.UUID("3b1948a2-2e1c-4d95-87fe-bc9b41eb8122")
    receipt = email_receipt_code(identifier)

    assert receipt == email_receipt_code(identifier)
    assert len(receipt) == 24
    assert receipt.count("-") == 4
