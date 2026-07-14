import base64

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from plane.app.views.user.email_security import EmailSecurityReceiptEndpoint
from plane.db.models import EmailOutbox
from plane.mailer.crypto import encrypt_bytes, keyed_digest
from plane.mailer.enums import DeliveryMode, MailPolicyClass, OutboxStatus
from plane.tests.factories import UserFactory

KEY = base64.urlsafe_b64encode(b"r" * 32).decode("ascii")
LOOKUP_KEY = base64.urlsafe_b64encode(b"h" * 32).decode("ascii")


def _outbox(user, receipt_code):
    outbox = EmailOutbox(
        recipient=user,
        recipient_email_hash=keyed_digest(user.email, purpose="recipient-email"),
        policy_class=MailPolicyClass.ACCOUNT_ACCESS,
        template_key="auth.magic_signin",
        audit_label="Login code",
        sender="Hangar <hello@hangar.example.com>",
        delivery_mode=DeliveryMode.CLEAR,
        payload_ciphertext="",
        idempotency_key=f"test:{receipt_code}",
        intent_digest="a" * 64,
        message_id=f"<{receipt_code}@hangar.example.com>",
        receipt_code=receipt_code,
        status=OutboxStatus.DELIVERED,
    )
    outbox.recipient_email_ciphertext = encrypt_bytes(
        user.email.encode(),
        associated_data=f"email-outbox-recipient:{outbox.id}".encode(),
    )
    outbox.save()
    return outbox


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OUTBOX_ENCRYPTION_KEYS=f"v1:{KEY}", EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
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
    assert "recipient_email_hash" not in response.data["results"][0]
