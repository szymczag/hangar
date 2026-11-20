# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Registration and assertion driven by a software authenticator.

Everything else about this feature is tested against stored state, which leaves
the part that actually matters — a signature py_webauthn will accept — assumed
rather than shown. plane/tests/support/webauthn_device.py performs the same
operations a security key does, with real ES256 keys and real signatures, so
these tests exercise the whole round trip: options out, credential in,
verification, session promoted.

What still needs a human is the browser layer: whether the panel calls
navigator.credentials correctly, and whether a given deployment's
relying-party ID satisfies the browser. That is a property of Chrome and of
DNS, not of this code.
"""

import json
import uuid
from io import StringIO
from unittest import mock

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, override_settings

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.db.models import Session, User
from plane.ext.auth.sessions import mint_admin_session, mint_app_session
from plane.ext.auth.webauthn import pending
from plane.ext.models import InstanceAdminWebAuthnCredential
from plane.ext.views import instance_webauthn
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import read_admin_session
from plane.tests.support.webauthn_device import SoftwareAuthenticator

setup_instance = _google_auth.setup_instance

ORIGIN = "http://localhost:3001"
SIGN_IN = "/api/instances/admins/sign-in/"
ME = "/api/instances/admins/me/"
REG_OPTIONS = "/api/instances/admins/webauthn/registration/options/"
REG_VERIFY = "/api/instances/admins/webauthn/registration/verify/"
AUTH_OPTIONS = "/api/instances/admins/webauthn/authentication/options/"
AUTH_VERIFY = "/api/instances/admins/webauthn/authentication/verify/"
PASSWORD = "correct-horse-battery-staple-42"
APP_ME = "/api/users/me/"


RP_ID = "localhost"
# Pinned so the origin the device signs for matches the one the server snapshots
# into the challenge; otherwise the test would depend on the ambient .env.
WEBAUTHN_SETTINGS = dict(
    ADMIN_BASE_URL="http://localhost:3001",
    ADMIN_BASE_PATH="/god-mode",
    WEB_URL="http://localhost:8000",
    WEBAUTHN_RP_ID=None,
    WEBAUTHN_ALLOWED_ORIGINS="",
)


@pytest.fixture
def admin_user(db, setup_instance):
    user = User.objects.create(email="admin@corp.com", username=uuid.uuid4().hex, is_password_autoset=False)
    user.set_password(PASSWORD)
    user.save()
    InstanceAdmin.objects.create(instance=setup_instance, user=user, role=20)
    return user


@pytest.fixture
def client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 test", HTTP_HOST="localhost:8000")


@pytest.fixture(autouse=True)
def _reset_throttles():
    """Each test drives several requests; they must not share a rate bucket."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def device():
    return SoftwareAuthenticator()


def _challenge_of(body):
    return json.loads(body["options"])["challenge"]


def _register(client, device, nickname="Test key"):
    body = client.post(REG_OPTIONS, {}, content_type="application/json").json()
    challenge = _challenge_of(body)
    credential = device.create(rp_id=RP_ID, challenge=challenge, origin=ORIGIN)
    return client.post(
        REG_VERIFY,
        {
            "credential": credential,
            "challenge": challenge,
            "user_handle": body["user_handle"],
            "nickname": nickname,
        },
        content_type="application/json",
    )


def _assert_with_key(client, device, origin=ORIGIN, sign_count=None):
    body = client.post(AUTH_OPTIONS, {}, content_type="application/json").json()
    challenge = _challenge_of(body)
    credential = device.get(rp_id=RP_ID, challenge=challenge, origin=origin, sign_count=sign_count)
    return client.post(
        AUTH_VERIFY,
        {"credential": credential, "challenge": challenge},
        content_type="application/json",
    )


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_real_key_completes_enrollment_and_opens_the_console(admin_user, client, device):
    """The whole first sign-in, with signatures py_webauthn actually verifies."""
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    assert client.get(ME).status_code in (401, 403)

    response = _register(client, device)

    assert response.status_code == 200, response.content
    assert InstanceAdminWebAuthnCredential.objects.filter(user=admin_user).count() == 1
    assert client.get(ME).status_code == 200


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_registered_key_authenticates_on_the_next_sign_in(admin_user, client, device):
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(client, device)
    client.post("/api/instances/admins/sign-out/")

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    assert client.get(ME).status_code in (401, 403)

    response = _assert_with_key(client, device)

    assert response.status_code == 200, response.content
    assert client.get(ME).status_code == 200
    assert read_admin_session(client).get(pending.VERIFIED_AT_KEY) is not None


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_another_administrators_key_is_refused(admin_user, client, device, setup_instance):
    """A valid signature from the wrong person's authenticator proves nothing."""
    intruder = User.objects.create(email="intruder@corp.com", username=uuid.uuid4().hex)
    InstanceAdmin.objects.create(instance=setup_instance, user=intruder, role=20)
    other_device = SoftwareAuthenticator()

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(client, device)
    client.post("/api/instances/admins/sign-out/")

    # The intruder enrolls their own key on their own account.
    intruder.set_password(PASSWORD)
    intruder.is_password_autoset = False
    intruder.save()
    intruder_client = Client(HTTP_USER_AGENT="Mozilla/5.0 test", HTTP_HOST="localhost:8000")
    intruder_client.post(SIGN_IN, {"email": intruder.email, "password": PASSWORD})
    _register(intruder_client, other_device)

    # Now they present it against the first administrator's pending sign-in.
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    body = client.post(AUTH_OPTIONS, {}, content_type="application/json").json()
    challenge = _challenge_of(body)
    forged = other_device.get(rp_id=RP_ID, challenge=challenge, origin=ORIGIN)

    response = client.post(AUTH_VERIFY, {"credential": forged, "challenge": challenge}, content_type="application/json")

    assert response.status_code == 400
    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_replayed_assertion_is_refused(admin_user, client, device):
    """The same signed assertion must not work twice."""
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(client, device)
    client.post("/api/instances/admins/sign-out/")

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    body = client.post(AUTH_OPTIONS, {}, content_type="application/json").json()
    challenge = _challenge_of(body)
    payload = {"credential": device.get(rp_id=RP_ID, challenge=challenge, origin=ORIGIN), "challenge": challenge}

    first = client.post(AUTH_VERIFY, payload, content_type="application/json")
    client.post("/api/instances/admins/sign-out/")
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    second = client.post(AUTH_VERIFY, payload, content_type="application/json")

    assert first.status_code == 200
    assert second.status_code == 400
    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_an_assertion_signed_for_another_origin_is_refused(admin_user, client, device):
    """clientDataJSON carries the origin, and it is checked server side."""
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(client, device)
    client.post("/api/instances/admins/sign-out/")

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})

    response = _assert_with_key(client, device, origin="https://evil.example.com")

    assert response.status_code == 400
    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_authenticator_is_detected_and_disabled(admin_user, client, device):
    """A counter that goes backwards is the signal a key was copied."""
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(client, device)
    client.post("/api/instances/admins/sign-out/")

    # Let the real key advance the counter.
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _assert_with_key(client, device)
    client.post("/api/instances/admins/sign-out/")

    credential = InstanceAdminWebAuthnCredential.objects.get(user=admin_user)
    stored = credential.sign_count
    assert stored > 0, "this authenticator does not use counters; the test proves nothing"

    # A clone still holds the old counter value.
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    response = _assert_with_key(client, device, sign_count=stored - 1)

    credential.refresh_from_db()
    assert response.status_code == 400
    assert credential.disabled_at is not None
    assert client.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_key_keeps_the_console_locked_until_a_shell_reset(admin_user, client, device):
    """After clone detection the password alone must not enroll a replacement.

    The whole path a deployment hit: the only key is disabled by a regressed
    counter, the next password sign-in is refused rather than sent to
    enrollment, nobody can register a key in its place, and the shell reset is
    what lets the administrator enroll again.
    """
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(client, device)
    client.post("/api/instances/admins/sign-out/")
    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _assert_with_key(client, device)
    client.post("/api/instances/admins/sign-out/")
    stored = InstanceAdminWebAuthnCredential.objects.get(user=admin_user).sign_count
    assert stored > 0, "this authenticator does not use counters; the test proves nothing"

    client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _assert_with_key(client, device, sign_count=stored - 1)
    assert InstanceAdminWebAuthnCredential.objects.get(user=admin_user).disabled_at is not None
    client.post("/api/instances/admins/sign-out/")

    # The next password sign-in is refused, not sent to enrollment.
    response = client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    assert "2fa" not in response.url
    assert "error_code=5198" in response.url
    assert read_admin_session(client).get(pending.PENDING_KEY) is None

    # And a replacement key cannot be registered around the refusal.
    new_key = SoftwareAuthenticator()
    refused = client.post(REG_OPTIONS, {}, content_type="application/json")
    assert refused.status_code == 409
    assert InstanceAdminWebAuthnCredential.objects.filter(user=admin_user).count() == 1
    assert client.get(ME).status_code in (401, 403)

    call_command("disable_instance_admin_2fa", email=admin_user.email, yes=True, stdout=StringIO())

    response = client.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    assert response.url.endswith("2fa/enroll/")
    enrolled = _register(client, new_key)
    assert enrolled.status_code == 200, enrolled.content
    assert client.get(ME).status_code == 200


# --- Clone detection ends the administrator's sessions ----------------------
#
# Whoever presents the copy also holds the password, and if they used it first
# they are signed in already. Disabling the key alone would only stop the next
# sign-in, so detection has to end what is open now.


def _new_client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 test", HTTP_HOST="localhost:8000")


def _sign_in_with_key(client, user, device, sign_count=None):
    client.post(SIGN_IN, {"email": user.email, "password": PASSWORD})
    return _assert_with_key(client, device, sign_count=sign_count)


def _enroll_and_advance(user, device):
    """Enroll the key and use it once, so the stored counter is above zero."""
    enrolling = _new_client()
    enrolling.post(SIGN_IN, {"email": user.email, "password": PASSWORD})
    _register(enrolling, device)
    enrolling.post("/api/instances/admins/sign-out/")
    first = _new_client()
    assert _sign_in_with_key(first, user, device).status_code == 200
    stored = InstanceAdminWebAuthnCredential.objects.get(user=user).sign_count
    assert stored > 0, "this authenticator does not use counters; the test proves nothing"
    return first, stored


def _sessions_of(user):
    return Session.objects.filter(user_id=str(user.id))


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_key_ends_the_console_session_opened_before_it(admin_user, device):
    """The session already signed in -- typically the copy's holder -- is ended."""
    signed_in, stored = _enroll_and_advance(admin_user, device)
    assert signed_in.get(ME).status_code == 200

    clone = _new_client()
    response = _sign_in_with_key(clone, admin_user, device, sign_count=stored - 1)

    assert response.status_code == 400
    assert response.json()["error_code"] == AUTHENTICATION_ERROR_CODES["ADMIN_2FA_VERIFICATION_FAILED"]
    assert signed_in.get(ME).status_code in (401, 403)
    assert clone.get(ME).status_code in (401, 403)
    assert not _sessions_of(admin_user).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_key_ends_the_administrators_application_sessions(admin_user, device):
    """The same password opens the application, so its sessions are suspect too."""
    _, stored = _enroll_and_advance(admin_user, device)
    app_key = mint_app_session(admin_user)
    app = _new_client()
    app.cookies[settings.SESSION_COOKIE_NAME] = app_key
    assert app.get(APP_ME).status_code == 200

    _sign_in_with_key(_new_client(), admin_user, device, sign_count=stored - 1)

    assert not Session.objects.filter(session_key=app_key).exists()
    assert app.get(APP_ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_key_leaves_other_users_sessions_alone(admin_user, device, setup_instance):
    bystander = User.objects.create(email="bystander@corp.com", username=uuid.uuid4().hex)
    InstanceAdmin.objects.create(instance=setup_instance, user=bystander, role=20)
    kept = {mint_app_session(bystander), mint_admin_session(bystander)}
    _, stored = _enroll_and_advance(admin_user, device)

    _sign_in_with_key(_new_client(), admin_user, device, sign_count=stored - 1)

    assert set(_sessions_of(bystander).values_list("session_key", flat=True)) == kept
    assert not _sessions_of(admin_user).exists()


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_key_discards_the_pending_sign_in_that_presented_it(admin_user, device):
    """The same pending state must not be able to try again."""
    _, stored = _enroll_and_advance(admin_user, device)
    clone = _new_client()

    _sign_in_with_key(clone, admin_user, device, sign_count=stored - 1)

    assert read_admin_session(clone).get(pending.PENDING_KEY) is None
    # Without a pending state there is nothing to ask a challenge for.
    retry = clone.post(AUTH_OPTIONS, {}, content_type="application/json")
    assert retry.status_code == 409
    assert clone.get(ME).status_code in (401, 403)


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_cloned_key_is_logged_with_the_sessions_it_ended(admin_user, device):
    _, stored = _enroll_and_advance(admin_user, device)
    mint_app_session(admin_user)
    credential = InstanceAdminWebAuthnCredential.objects.get(user=admin_user)

    with mock.patch.object(instance_webauthn.security_logger, "warning") as warning:
        _sign_in_with_key(_new_client(), admin_user, device, sign_count=stored - 1)

    warning.assert_called_once()
    message, *args = warning.call_args.args
    assert "regressed" in message
    assert args == [credential.id, 2]


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_normal_sign_in_with_the_key_ends_no_session(admin_user, device):
    signed_in, _ = _enroll_and_advance(admin_user, device)
    app_key = mint_app_session(admin_user)

    second = _new_client()
    response = _sign_in_with_key(second, admin_user, device)

    assert response.status_code == 200
    assert signed_in.get(ME).status_code == 200
    assert second.get(ME).status_code == 200
    assert Session.objects.filter(session_key=app_key).exists()
    assert InstanceAdminWebAuthnCredential.objects.get(user=admin_user).disabled_at is None


@pytest.mark.unit
@pytest.mark.django_db
@override_settings(**WEBAUTHN_SETTINGS)
def test_a_key_without_a_counter_ends_no_session(admin_user, device):
    """A counter stuck at zero is not a clone, so nothing is ended."""
    enrolling = _new_client()
    enrolling.post(SIGN_IN, {"email": admin_user.email, "password": PASSWORD})
    _register(enrolling, device)
    enrolling.post("/api/instances/admins/sign-out/")
    first = _new_client()
    assert _sign_in_with_key(first, admin_user, device, sign_count=0).status_code == 200
    app_key = mint_app_session(admin_user)

    second = _new_client()
    response = _sign_in_with_key(second, admin_user, device, sign_count=0)

    assert response.status_code == 200
    assert first.get(ME).status_code == 200
    assert Session.objects.filter(session_key=app_key).exists()
    credential = InstanceAdminWebAuthnCredential.objects.get(user=admin_user)
    assert credential.sign_count == 0
    assert credential.disabled_at is None
