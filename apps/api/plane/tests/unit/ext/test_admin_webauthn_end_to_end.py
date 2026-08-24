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

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from plane.db.models import User
from plane.ext.auth.webauthn import pending
from plane.ext.models import InstanceAdminWebAuthnCredential
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
