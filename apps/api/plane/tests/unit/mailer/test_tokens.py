# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import re

import pytest
from django.test import override_settings

from plane.mailer.tokens import email_idempotency_token, email_receipt_code


@pytest.mark.unit
def test_email_receipts_are_random_and_transcription_safe():
    receipts = {email_receipt_code() for _ in range(100)}

    assert len(receipts) == 100
    assert all(re.fullmatch(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){4}", receipt) for receipt in receipts)


@pytest.mark.unit
@override_settings(SECRET_KEY="idempotency-test-secret")
def test_sensitive_idempotency_inputs_use_stable_purpose_separated_hmacs():
    first = email_idempotency_token("magic-signin", "request-key", "123456")
    replay = email_idempotency_token("magic-signin", "request-key", "123456")
    different_purpose = email_idempotency_token("email-update-code", "request-key", "123456")
    with override_settings(SECRET_KEY="different-idempotency-secret"):
        different_secret = email_idempotency_token("magic-signin", "request-key", "123456")

    assert first == replay
    assert first != different_purpose
    assert first != different_secret
    assert len(first) == 64
    assert "123456" not in first
