# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from plane.app.views.user.email_security import EmailSecurityReceiptEndpoint
from plane.db.models import EmailOutbox
from plane.mailer.enums import DeliveryMode, MailPolicyClass, OutboxStatus
from plane.tests.factories import UserFactory


def _outbox(user, receipt_code):
    return EmailOutbox.objects.create(
        recipient=user,
        recipient_email=user.email,
        policy_class=MailPolicyClass.ACCOUNT_ACCESS,
        template_key="auth.magic_signin",
        audit_label="Login code",
        sender="Hangar <hello@hangar.example.com>",
        delivery_mode=DeliveryMode.CLEAR,
        encrypted_message=b"",
        idempotency_key=f"test:{receipt_code}",
        message_id=f"<{receipt_code}@hangar.example.com>",
        receipt_code=receipt_code,
        status=OutboxStatus.DELIVERED,
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_user_receipt_ledger_is_self_scoped_and_searchable():
    user = UserFactory(email="person@example.com", username="person@example.com")
    other = UserFactory(email="other@example.com", username="other@example.com")
    own = _outbox(user, "AAAA-BBBB-CCCC-DDDD-EEEE")
    _outbox(other, "FFFF-1111-2222-3333-4444")
    request = APIRequestFactory().get("/api/users/me/email-security/receipts/", {"receipt": own.receipt_code})
    force_authenticate(request, user=user)

    response = EmailSecurityReceiptEndpoint.as_view()(request)

    assert response.status_code == 200
    assert [row["receipt_code"] for row in response.data["results"]] == [own.receipt_code]
    assert "recipient_email" not in response.data["results"][0]
