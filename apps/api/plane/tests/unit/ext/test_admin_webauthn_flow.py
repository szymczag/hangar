# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The properties that make a mandatory second factor worth having.

The cryptography itself is py_webauthn's job. What is tested here is everything
around it: that a password alone opens nothing, that a half-finished sign-in
grants no access, and that the pieces which could quietly become no-ops —
challenge single use, session binding, attempt limits — actually hold.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from plane.db.models import User
from plane.ext.auth.webauthn import pending
from plane.ext.models import InstanceAdminWebAuthnChallenge, InstanceAdminWebAuthnCredential
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import (
    authenticate_admin,
    read_admin_session as admin_session,
    store_admin_session as save_admin_session,
)

setup_instance = _google_auth.setup_instance

SIGN_IN = "/api/instances/admins/sign-in/"
ME = "/api/instances/admins/me/"
SESSION = "/api/instances/admins/session/"
PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture
def admin_user(db, setup_instance):
    user = User.objects.create(email="admin@corp.com", username=uuid.uuid4().hex, is_password_autoset=False)
    user.set_password(PASSWORD)
    user.save()
    InstanceAdmin.objects.create(instance=setup_instance, user=user, role=20)
    return user


def _credential(user, **overrides):
    values = {
        "credential_id": uuid.uuid4().hex,
        "public_key": uuid.uuid4().hex,
        "sign_count": 0,
        "user_handle": uuid.uuid4().hex,
        "nickname": f"key-{uuid.uuid4().hex[:6]}",
    }
    values.update(overrides)
    return InstanceAdminWebAuthnCredential.objects.create(user=user, **values)


@pytest.fixture
def client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 test")


@pytest.mark.unit
@pytest.mark.django_db
def test_a_correct_password_does_not_create_a_session(admin_user, client):
    """The core property: the password step stops short of logging in."""
    response = client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    assert response.status_code == 302
    assert "2fa" in response.url
    session = admin_session(client)
    assert "_auth_user_id" not in session
    assert session.get(pending.PENDING_KEY) is not None


@pytest.mark.unit
@pytest.mark.django_db
def test_a_pending_session_cannot_reach_the_console(admin_user, client):
    """Anonymous by construction, so every panel endpoint refuses."""
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
def test_a_pending_session_is_reported_so_the_console_knows_the_step(admin_user, client):
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    body = client.get(SESSION).json()

    assert body["is_authenticated"] is False
    assert body["is_2fa_pending"] is True
    assert body["requires_enrollment"] is True
    assert body["email"] == admin_user.email


@pytest.mark.unit
@pytest.mark.django_db
def test_an_administrator_with_a_key_is_sent_to_the_assertion_step(admin_user, client):
    _credential(admin_user)

    response = client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    assert response.url.endswith("2fa/")
    assert client.get(SESSION).json()["requires_enrollment"] is False


@pytest.mark.unit
@pytest.mark.django_db
def test_a_disabled_credential_does_not_count_as_enrolled(admin_user, client):
    """A cloned key is disabled, and must not leave the account unprotected."""
    _credential(admin_user, disabled_at=timezone.now())

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    assert client.get(SESSION).json()["requires_enrollment"] is True


@pytest.mark.unit
@pytest.mark.django_db
def test_a_session_without_the_verification_marker_is_refused(admin_user, client):
    """Guards every future path that might mint an admin session.

    Sessions that existed before this shipped carry no marker either, which is
    why deploying it signs administrators out.
    """
    authenticate_admin(client, admin_user, verified=False)

    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
def test_a_verified_session_reaches_the_console(admin_user, client):
    """Positive control: the gate must not simply deny everything."""
    authenticate_admin(client, admin_user, verified=True)

    assert client.get(ME).status_code == 200


@pytest.mark.unit
@pytest.mark.django_db
def test_a_stale_verification_marker_stops_working(admin_user, client):
    session = authenticate_admin(client, admin_user, verified=False)
    session[pending.VERIFIED_AT_KEY] = (timezone.now() - timedelta(days=2)).isoformat()
    save_admin_session(client, session)

    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(ADMIN_WEBAUTHN_REQUIRED=False)
def test_the_operator_escape_hatch_restores_password_only_sign_in(admin_user, client):
    """Exists so a lockout is recoverable without a code change."""
    response = client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    assert response.status_code == 302
    assert "2fa" not in response.url
    assert "_auth_user_id" in admin_session(client)
    assert client.get(ME).status_code == 200


@pytest.mark.unit
@pytest.mark.django_db
def test_pending_state_expires(admin_user, client):
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    session = admin_session(client)
    blob = session[pending.PENDING_KEY]
    blob["started_at"] = (timezone.now() - timedelta(hours=2)).isoformat()
    session[pending.PENDING_KEY] = blob
    save_admin_session(client, session)

    response = client.post("/api/instances/admins/webauthn/registration/options/", {}, content_type="application/json")

    assert response.status_code == 409


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(ADMIN_2FA_MAX_ATTEMPTS=2)
def test_exhausting_attempts_destroys_the_pending_state(admin_user, client):
    """Guessing cannot continue indefinitely inside one pending window."""
    _credential(admin_user)
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    session = admin_session(client)
    blob = session[pending.PENDING_KEY]
    blob["attempts"] = 2
    session[pending.PENDING_KEY] = blob
    save_admin_session(client, session)

    response = client.post(
        "/api/instances/admins/webauthn/authentication/options/", {}, content_type="application/json"
    )

    assert response.status_code == 409
    assert admin_session(client).get(pending.PENDING_KEY) is None


@pytest.mark.unit
@pytest.mark.django_db
def test_a_challenge_can_only_be_consumed_once(admin_user, client):
    """Single use is enforced by a conditional UPDATE, not read-then-write."""
    from plane.ext.views.instance_webauthn import _WebAuthnBase

    challenge = InstanceAdminWebAuthnChallenge.objects.create(
        user=admin_user,
        purpose=InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION,
        challenge="abc",
        session_key="sess",
        rp_id="localhost",
        origin="http://localhost",
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    view = _WebAuthnBase()

    class _Req:
        session = type("S", (), {"session_key": "sess"})()

    first = view._consume_challenge(_Req(), admin_user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION, "abc")
    second = view._consume_challenge(_Req(), admin_user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION, "abc")

    assert first is not None and first.id == challenge.id
    assert second is None


@pytest.mark.unit
@pytest.mark.django_db
def test_a_challenge_issued_to_another_session_is_refused(admin_user):
    from plane.ext.views.instance_webauthn import _WebAuthnBase

    InstanceAdminWebAuthnChallenge.objects.create(
        user=admin_user,
        purpose=InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION,
        challenge="xyz",
        session_key="the-issuing-session",
        rp_id="localhost",
        origin="http://localhost",
        expires_at=timezone.now() + timedelta(minutes=5),
    )

    class _Req:
        session = type("S", (), {"session_key": "a-different-session"})()

    assert (
        _WebAuthnBase()._consume_challenge(
            _Req(), admin_user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION, "xyz"
        )
        is None
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_a_registration_challenge_cannot_satisfy_an_assertion(admin_user):
    """Stage confusion: the two purposes must not be interchangeable."""
    from plane.ext.views.instance_webauthn import _WebAuthnBase

    InstanceAdminWebAuthnChallenge.objects.create(
        user=admin_user,
        purpose=InstanceAdminWebAuthnChallenge.Purpose.REGISTRATION,
        challenge="reg",
        session_key="sess",
        rp_id="localhost",
        origin="http://localhost",
        expires_at=timezone.now() + timedelta(minutes=5),
    )

    class _Req:
        session = type("S", (), {"session_key": "sess"})()

    assert (
        _WebAuthnBase()._consume_challenge(
            _Req(), admin_user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION, "reg"
        )
        is None
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_an_expired_challenge_is_refused(admin_user):
    from plane.ext.views.instance_webauthn import _WebAuthnBase

    InstanceAdminWebAuthnChallenge.objects.create(
        user=admin_user,
        purpose=InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION,
        challenge="old",
        session_key="sess",
        rp_id="localhost",
        origin="http://localhost",
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    class _Req:
        session = type("S", (), {"session_key": "sess"})()

    assert (
        _WebAuthnBase()._consume_challenge(
            _Req(), admin_user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION, "old"
        )
        is None
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_a_credential_id_cannot_be_registered_to_two_administrators(admin_user, setup_instance):
    """Enforced by the database, not by a check a view could forget."""
    from django.db import IntegrityError

    other = User.objects.create(email="other@corp.com", username=uuid.uuid4().hex)
    _credential(admin_user, credential_id="shared-id")

    with pytest.raises(IntegrityError):
        _credential(other, credential_id="shared-id")


# ---------------------------------------------------------------------------
# Regressions found in review
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
def test_starting_a_pending_state_does_not_inherit_the_previous_session(admin_user, client):
    """cycle_key kept the old contents, so a verified session survived beneath.

    Once the pending state expired and was cleared, that session reappeared —
    fully verified, belonging to whoever signed in previously.
    """
    authenticate_admin(client, admin_user, verified=True)
    assert client.get(ME).status_code == 200

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    session = admin_session(client)
    assert "_auth_user_id" not in session
    assert session.get(pending.VERIFIED_AT_KEY) is None


@pytest.mark.unit
@pytest.mark.django_db
def test_signing_out_of_a_pending_state_clears_it(admin_user, client):
    """"Start over" left the blob — and its attempt count — in place.

    The sign-out view looked up request.user.id first, which raises for the
    anonymous pending caller, so logout() never ran.
    """
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    assert admin_session(client).get(pending.PENDING_KEY) is not None

    client.post("/api/instances/admins/sign-out/")

    assert admin_session(client).get(pending.PENDING_KEY) is None


@pytest.mark.unit
@pytest.mark.django_db
def test_a_verified_administrator_can_request_registration_options(admin_user, client):
    """Adding a second key must be reachable.

    authentication_classes = [] made request.user permanently anonymous, so
    this branch could never run — and with the last-credential rule refusing
    removal, there was no way to rotate a key at all.
    """
    _credential(admin_user)
    authenticate_admin(client, admin_user, verified=True)

    response = client.post(
        "/api/instances/admins/webauthn/registration/options/", {}, content_type="application/json"
    )

    assert response.status_code == 200
    assert "options" in response.json()


@pytest.mark.unit
@pytest.mark.django_db
def test_issuing_a_challenge_clears_the_spent_ones(admin_user, client):
    """Every options request used to leave a row behind permanently."""
    from plane.ext.views.instance_webauthn import _WebAuthnBase

    InstanceAdminWebAuthnChallenge.objects.create(
        user=admin_user,
        purpose=InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION,
        challenge="spent",
        session_key="sess",
        rp_id="localhost",
        origin="http://localhost",
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    class _Req:
        session = type("S", (), {"session_key": "sess"})()

    _WebAuthnBase()._issue_challenge(
        _Req(), admin_user, InstanceAdminWebAuthnChallenge.Purpose.AUTHENTICATION
    )

    assert not InstanceAdminWebAuthnChallenge.objects.filter(challenge="spent").exists()
    assert InstanceAdminWebAuthnChallenge.objects.filter(user=admin_user).count() == 1


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(SESSION_SAVE_EVERY_REQUEST=True)
def test_a_rolling_session_keeps_its_verification(admin_user, client):
    """The cookie rolls on every request; an absolute marker deadline did not.

    An administrator working continuously was cut off at exactly
    ADMIN_SESSION_COOKIE_AGE, with a valid session and no pending state to
    drive the second-factor page.
    """
    session = authenticate_admin(client, admin_user, verified=False)
    session[pending.VERIFIED_AT_KEY] = (timezone.now() - timedelta(days=2)).isoformat()
    save_admin_session(client, session)

    assert client.get(ME).status_code == 200

