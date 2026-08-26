# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from plane.app.views.user.email_security import (
    EmailSecurityChallengeEndpoint,
    EmailSecurityChallengeVerifyEndpoint,
    EmailSecurityKeyUploadEndpoint,
    EmailSecurityTestEndpoint,
)
from plane.db.models import OpenPGPKeyChallenge, UserOpenPGPKey
from plane.mailer.enums import OpenPGPKeyStatus
from plane.mailer.exceptions import OpenPGPError
from plane.mailer.openpgp import OpenPGPCertificateInfo
from plane.tests.factories import UserFactory


def _key(user, version, status):
    return UserOpenPGPKey.objects.create(
        user=user,
        version=version,
        certificate="public certificate",
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
        token_digest=make_password(code),
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
@override_settings(EMAIL_OPENPGP_ENABLED=True)
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
@override_settings(EMAIL_OPENPGP_ENABLED=True)
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


UPLOAD_PASSWORD = "correct-horse-battery-staple-42"


def _upload(user, certificate="-----BEGIN PGP PUBLIC KEY BLOCK-----"):
    # Changing a key demands the current password, as it does for a real client.
    request = APIRequestFactory().post(
        "/keys/", {"certificate": certificate, "password": UPLOAD_PASSWORD}, format="json"
    )
    # A verified password stamps the session, so one has to exist.
    request.session = SessionStore()
    force_authenticate(request, user=user)
    return EmailSecurityKeyUploadEndpoint.as_view()(request)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=False, EMAIL_DELIVERY_V2_ENABLED=True)
def test_a_key_can_be_enrolled_before_the_instance_switches_encryption_on():
    """Otherwise nobody can be ready on the day it is switched on.

    Gating enrolment on the feature meant the first encrypted send always went
    out to people with no key — that is, in the clear.
    """
    user = UserFactory(is_password_autoset=False)
    user.set_password(UPLOAD_PASSWORD)
    user.save()
    inspected = OpenPGPCertificateInfo(
        normalized_certificate="-----BEGIN PGP PUBLIC KEY BLOCK-----",
        primary_fingerprint="A" * 40,
        encryption_subkey_fingerprint="B" * 40,
        primary_algorithm="RSA",
        encryption_algorithm="RSA",
        encryption_key_size=3072,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=365),
    )
    with patch("plane.app.views.user.email_security.inspect_certificate", return_value=inspected):
        response = _upload(user)

    assert response.status_code == 201
    assert UserOpenPGPKey.objects.filter(user=user, status=OpenPGPKeyStatus.PENDING).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=False, EMAIL_DELIVERY_V2_ENABLED=True)
def test_the_verification_challenge_is_encrypted_even_while_the_feature_is_off():
    """The property that makes enrolling early safe rather than theatre.

    A challenge proves possession of the private key only if the code was
    unreadable in transit. The mailer treats an explicitly named key as reason
    enough to encrypt, independently of the instance flag — if that ever
    changed, verification would degrade into emailing a plaintext code.
    """
    user = UserFactory()
    key = _key(user, 1, OpenPGPKeyStatus.PENDING)

    request = APIRequestFactory().post("/challenge/")
    force_authenticate(request, user=user)
    with patch("plane.app.views.user.email_security.enqueue_rendered_email") as enqueue:
        enqueue.return_value = type("R", (), {"outbox_id": uuid.uuid4()})()
        EmailSecurityChallengeEndpoint.as_view()(request, key_id=key.id)

    assert enqueue.call_args.kwargs["encryption_key"] == key


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=False, EMAIL_DELIVERY_V2_ENABLED=False)
def test_verification_is_refused_rather_than_sent_in_the_clear():
    """Without durable delivery the mailer cannot encrypt at all."""
    user = UserFactory()
    key = _key(user, 1, OpenPGPKeyStatus.PENDING)

    request = APIRequestFactory().post("/challenge/")
    force_authenticate(request, user=user)
    response = EmailSecurityChallengeEndpoint.as_view()(request, key_id=key.id)

    assert response.status_code == 409
    assert "durable email delivery" in response.data["error"]
    assert not OpenPGPKeyChallenge.objects.filter(key=key).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(EMAIL_OPENPGP_ENABLED=False, EMAIL_DELIVERY_V2_ENABLED=True)
def test_a_test_message_still_requires_the_feature():
    """This one really does send encrypted mail, so it stays gated."""
    user = UserFactory()
    key = _key(user, 1, OpenPGPKeyStatus.ACTIVE)

    request = APIRequestFactory().post("/test/")
    force_authenticate(request, user=user)
    response = EmailSecurityTestEndpoint.as_view()(request, key_id=key.id)

    assert response.status_code == 409
