# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Administrator control over someone else's encryption key.

The feature is the ability to decide which certificate a person's mail is
encrypted to. Whoever holds that can arrange to read it, so these tests are as
much about the record being written as about the key being set.
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import User, UserOpenPGPKey
from plane.ext.models import OpenPGPAdminAction, UserOpenPGPPolicy
from plane.license.models import InstanceAdmin
from plane.mailer.enums import OpenPGPKeyStatus
from plane.mailer.exceptions import OpenPGPError
from plane.mailer.openpgp import OpenPGPCertificateInfo
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin

setup_instance = _google_auth.setup_instance

CERTIFICATE = "-----BEGIN PGP PUBLIC KEY BLOCK-----"


def _url(user):
    return f"/api/instances/users/{user.id}/openpgp/"


def _inspected(fingerprint="A" * 40):
    return OpenPGPCertificateInfo(
        normalized_certificate=CERTIFICATE,
        primary_fingerprint=fingerprint,
        encryption_subkey_fingerprint="B" * 40,
        primary_algorithm="RSA",
        encryption_algorithm="RSA",
        encryption_key_size=3072,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=365),
    )


def _user(email):
    return User.objects.create(email=email, username=uuid.uuid4().hex)


@pytest.fixture
def subject(db):
    return _user("person@corp.com")


@pytest.fixture
def admin_client(db, setup_instance):
    admin = _user("admin@ops.example")
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    return client


def _set_key(client, subject, fingerprint="A" * 40, note="escrow"):
    with (
        patch("plane.ext.views.instance_openpgp.inspect_certificate", return_value=_inspected(fingerprint)),
        patch("plane.ext.views.instance_openpgp._send_key_changed_alert") as alert,
    ):
        response = client.post(_url(subject), {"certificate": CERTIFICATE, "note": note}, format="json")
    return response, alert


@pytest.mark.contract
@pytest.mark.django_db
def test_an_ordinary_account_cannot_reach_this(subject):
    plain = APIClient()
    plain.force_authenticate(user=_user("nobody@corp.com"))

    assert plain.get(_url(subject)).status_code in (401, 403)
    assert APIClient().get(_url(subject)).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_admin_session_without_the_second_factor_is_refused(db, setup_instance, subject):
    """This endpoint decides whose mail an administrator can read."""
    admin = _user("admin2@ops.example")
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    client.force_authenticate(user=admin)  # no WebAuthn marker

    assert client.get(_url(subject)).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_setting_a_key_activates_it_and_records_who_did_it(admin_client, subject):
    response, alert = _set_key(admin_client, subject)

    assert response.status_code == 200
    key = UserOpenPGPKey.objects.get(user=subject)
    assert key.status == OpenPGPKeyStatus.ACTIVE
    # No challenge was issued: the administrator vouched for the certificate.
    assert key.verified_at is not None

    record = OpenPGPAdminAction.objects.get(subject=subject)
    assert record.action == OpenPGPAdminAction.Action.KEY_SET
    assert record.primary_fingerprint == "A" * 40
    assert record.note == "escrow"
    assert record.actor is not None
    alert.assert_called_once()


@pytest.mark.contract
@pytest.mark.django_db
def test_the_record_of_an_administrative_action_cannot_be_altered(admin_client, subject):
    """Its value is that it cannot be tidied away afterwards."""
    _set_key(admin_client, subject)
    record = OpenPGPAdminAction.objects.get(subject=subject)

    record.note = "something else"
    with pytest.raises(ValidationError):
        record.save()
    with pytest.raises(ValidationError):
        record.delete()


@pytest.mark.contract
@pytest.mark.django_db
def test_replacing_a_key_supersedes_the_previous_one(admin_client, subject):
    _set_key(admin_client, subject, fingerprint="A" * 40)
    _set_key(admin_client, subject, fingerprint="C" * 40)

    assert UserOpenPGPKey.objects.filter(user=subject, status=OpenPGPKeyStatus.ACTIVE).count() == 1
    assert UserOpenPGPKey.objects.get(user=subject, primary_fingerprint="A" * 40).status == OpenPGPKeyStatus.REPLACED


@pytest.mark.contract
@pytest.mark.django_db
def test_a_certificate_that_cannot_be_read_gives_one_answer(admin_client, subject):
    """Not an oracle for probing what a certificate contains."""
    with patch("plane.ext.views.instance_openpgp.inspect_certificate", side_effect=OpenPGPError("gpg said no")):
        response = admin_client.post(_url(subject), {"certificate": CERTIFICATE}, format="json")

    assert response.status_code == 400
    assert "gpg" not in response.data["error"]
    assert not UserOpenPGPKey.objects.filter(user=subject).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_locking_stops_the_account_from_changing_its_own_key(admin_client, subject):
    response = admin_client.patch(_url(subject), {"is_locked": True, "note": "escrow"}, format="json")

    assert response.status_code == 200
    assert response.data["is_locked"] is True
    policy = UserOpenPGPPolicy.objects.get(user=subject)
    assert policy.is_locked is True
    assert policy.locked_by is not None
    assert OpenPGPAdminAction.objects.filter(subject=subject, action=OpenPGPAdminAction.Action.LOCKED).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_unlocking_returns_the_account_to_self_service(admin_client, subject):
    admin_client.patch(_url(subject), {"is_locked": True}, format="json")
    response = admin_client.patch(_url(subject), {"is_locked": False}, format="json")

    assert response.data["is_locked"] is False
    assert UserOpenPGPPolicy.objects.get(user=subject).locked_at is None
    assert OpenPGPAdminAction.objects.filter(subject=subject, action=OpenPGPAdminAction.Action.UNLOCKED).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_the_lock_state_must_be_stated_explicitly(admin_client, subject):
    assert admin_client.patch(_url(subject), {"note": "no verb"}, format="json").status_code == 400
    assert admin_client.patch(_url(subject), {"is_locked": "yes"}, format="json").status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unknown_account_is_not_created_by_asking_for_it(admin_client):
    missing = uuid.uuid4()

    assert admin_client.get(f"/api/instances/users/{missing}/openpgp/").status_code == 404
    assert (
        admin_client.patch(f"/api/instances/users/{missing}/openpgp/", {"is_locked": True}, format="json").status_code
        == 404
    )
    assert not UserOpenPGPPolicy.objects.exists()
