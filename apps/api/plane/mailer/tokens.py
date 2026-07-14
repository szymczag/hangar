# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Random public identifiers used by the outbound email ledger."""

import secrets
import re

from django.utils.crypto import salted_hmac


def email_receipt_code() -> str:
    """Return an unguessable 80-bit receipt code formatted for transcription."""

    raw = secrets.token_hex(10).upper()
    return "-".join(raw[index : index + 4] for index in range(0, len(raw), 4))


def email_idempotency_token(purpose: str, *parts: object) -> str:
    """Bind sensitive delivery inputs to an opaque, purpose-separated identifier."""

    if not re.fullmatch(r"[a-z0-9._-]{1,64}", purpose):
        raise ValueError("Email idempotency purpose is invalid")
    payload = "\x00".join(str(part) for part in parts)
    return salted_hmac(f"hangar.email.idempotency.{purpose}", payload, algorithm="sha256").hexdigest()
