# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from plane.app.views.user.email_security import EmailSecurityChallengeVerifyEndpoint, EmailSecurityKeyUploadEndpoint
from plane.db.models import OpenPGPKeyChallenge, UserOpenPGPKey
from plane.mailer.crypto import keyed_digest
from plane.mailer.enums import OpenPGPKeyStatus
from plane.mailer.exceptions import OpenPGPError
from plane.tests.factories import UserFactory

LOOKUP_KEY = base64.urlsafe_b64encode(b"k" * 32).decode("ascii")


def _key(user, version, status):
    return UserOpenPGPKey.objects.create(
        user=user,
        version=version,
        certificate_ciphertext="encrypted-public-certificate",
        primary_fingerprint=f"{version:040X}",
        encryption_subkey_fingerprint=f"{version + 100:040X}",
        primary_algorithm="RSA",
        encryption_algorithm="RSA",
        encryption_key_size=3072,
        key_expires_at=timezone.now() + timedelta(days=1),
        status=status,
    )


def _challenge(key, code="ABCD2345EFGH6789"):
    challenge_id = uuid.uuid4()
    return OpenPGPKeyChallenge.objects.create(
        id=challenge_id,
        key=key,
        token_digest=keyed_digest(code, purpose=f"openpgp-challenge:{challenge_id}"),
        expires_at=timezone.now() + timedelta(minutes=15),
        sent_at=timezone.now(),
    )


def _verify(user, key, code):
    request = APIRequestFactory().post("/verify/", {"code": code}, format="json")
    force_authenticate(request, user=user)
    with patch("plane.app.views.user.email_security._send_key_changed_alert"):
        return EmailSecurityChallengeVerifyEndpoint.as_view()(request, key_id=key.id)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=True, EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
def test_verified_replacement_is_atomic_and_challenge_cannot_be_replayed():
    user = UserFactory(email="key-owner@example.com", username="key-owner@example.com")
    active = _key(user, 1, OpenPGPKeyStatus.ACTIVE)
    pending = _key(user, 2, OpenPGPKeyStatus.PENDING)
    challenge = _challenge(pending)

    response = _verify(user, pending, "ABCD2345EFGH6789")

    assert response.status_code == 200
    active.refresh_from_db()
    pending.refresh_from_db()
    challenge.refresh_from_db()
    assert active.status == OpenPGPKeyStatus.REPLACED
    assert pending.status == OpenPGPKeyStatus.ACTIVE
    assert challenge.consumed_at is not None

    replay = _verify(user, pending, "ABCD2345EFGH6789")
    assert replay.status_code == 400


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=True, EMAIL_LOOKUP_HMAC_KEY=LOOKUP_KEY)
def test_challenge_is_consumed_after_five_failed_attempts():
    user = UserFactory(email="attempts@example.com", username="attempts@example.com")
    pending = _key(user, 1, OpenPGPKeyStatus.PENDING)
    challenge = _challenge(pending)

    for _attempt in range(5):
        response = _verify(user, pending, "WRONG2345CODE678")
        assert response.status_code == 400

    challenge.refresh_from_db()
    assert challenge.attempts == 5
    assert challenge.consumed_at is not None

    correct_after_lockout = _verify(user, pending, "ABCD2345EFGH6789")
    assert correct_after_lockout.status_code == 400


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=True)
def test_key_upload_never_exposes_openpgp_exception_details():
    user = UserFactory(
        email="upload-owner@example.com",
        username="upload-owner@example.com",
        is_password_autoset=True,
    )
    request = APIRequestFactory().post(
        "/api/users/me/email-security/keys/",
        {"certificate": "-----BEGIN PGP PUBLIC KEY BLOCK-----"},
        format="json",
    )
    request.session = {"reauthenticated_at": timezone.now().isoformat()}
    force_authenticate(request, user=user)

    with patch(
        "plane.app.views.user.email_security.inspect_certificate",
        side_effect=OpenPGPError("INTERNAL_PARSER_SENTINEL"),
    ):
        response = EmailSecurityKeyUploadEndpoint.as_view()(request)

    assert response.status_code == 400
    assert response.data == {
        "error": (
            "The public certificate could not be accepted. Verify that it is a valid ASCII-armored OpenPGP public "
            "certificate with a supported encryption key."
        )
    }
    assert "INTERNAL_PARSER_SENTINEL" not in str(response.data)
