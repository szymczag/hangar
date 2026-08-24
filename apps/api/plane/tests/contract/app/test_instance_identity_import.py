# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The console upload decides who may sign in as an existing account.

Every test here is about a way that could go wrong, not about the happy path:
who may reach it, what it refuses, and whether the file that gets applied is
the file that was shown.
"""

import io
import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import FederatedIdentity, FederatedIdentityImportAudit, User
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.ext.services.federated_import import REFUSAL_MESSAGES
from plane.tests.support.admin_session import authenticate_admin

setup_instance = _google_auth.setup_instance

URL = "/api/instances/identity-import/"
ISSUER = "https://accounts.google.com"
PASSWORD = "correct-horse-battery-staple-42"


def _csv(*rows):
    lines = ["email,subject,subject_format"]
    lines.extend(f"{email},{subject},{fmt}" for email, subject, fmt in rows)
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    upload = io.BytesIO(payload)
    upload.name = "mappings.csv"
    return upload


def _user(email, *, password=None):
    user = User.objects.create(email=email, username=uuid.uuid4().hex, is_password_autoset=password is None)
    if password:
        user.set_password(password)
        user.save()
    return user


@pytest.fixture
def admin(db, setup_instance):
    account = _user("admin@ops.example", password=PASSWORD)
    InstanceAdmin.objects.create(instance=setup_instance, user=account, role=20)
    return account


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    authenticate_admin(client, admin)
    return client


def _preview(client, upload, **extra):
    return client.post(
        URL,
        {"file": upload, "provider": "google", "issuer": ISSUER, **extra},
        format="multipart",
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_anonymous_and_ordinary_accounts_are_refused(db, setup_instance):
    assert APIClient().get(URL).status_code in (401, 403)

    ordinary = APIClient()
    ordinary.force_authenticate(user=_user("nobody@corp.com"))
    assert ordinary.get(URL).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_admin_session_without_the_second_factor_is_refused(admin):
    """The console's own permission enforces this; pinned so it stays true here.

    This endpoint is the reason the second factor was built, so a session that
    skipped it must not reach the upload even though the account is an admin.
    """
    client = APIClient()
    client.force_authenticate(user=admin)  # no WebAuthn marker in the session

    assert client.get(URL).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_preview_writes_nothing_and_returns_a_grant(admin_client):
    _user("person@corp.com")

    response = _preview(admin_client, _csv(("person@corp.com", "sub-1", "")))

    assert response.status_code == 200
    assert response.data["valid"] is True
    assert response.data["report"]["imported_count"] == 1
    assert response.data["rows"][0]["email"] == "person@corp.com"
    assert response.data["grant"]
    assert FederatedIdentity.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_confirming_applies_the_import_and_records_an_audit(admin_client):
    person = _user("person@corp.com")
    grant = _preview(admin_client, _csv(("person@corp.com", "sub-1", ""))).data["grant"]

    response = _preview(
        admin_client,
        _csv(("person@corp.com", "sub-1", "")),
        confirm="true",
        grant=grant,
        password=PASSWORD,
    )

    assert response.status_code == 200
    assert FederatedIdentity.objects.filter(user=person, subject="sub-1").exists()
    audit = FederatedIdentityImportAudit.objects.get()
    assert audit.imported_count == 1
    assert audit.report["actor_id"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_grant_does_not_carry_over_to_a_different_file(admin_client):
    """The property that makes uploading twice safe.

    Preview an innocuous file, then confirm a different one with the grant it
    produced. Without the digest binding, this is how the operator reviews one
    file and applies another.
    """
    _user("person@corp.com")
    victim = _user("victim@corp.com")
    grant = _preview(admin_client, _csv(("person@corp.com", "sub-1", ""))).data["grant"]

    response = _preview(
        admin_client,
        _csv(("victim@corp.com", "attacker-subject", "")),
        confirm="true",
        grant=grant,
        password=PASSWORD,
    )

    assert response.status_code == 409
    assert not FederatedIdentity.objects.filter(user=victim).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_confirming_without_the_password_changes_nothing(admin_client):
    _user("person@corp.com")
    grant = _preview(admin_client, _csv(("person@corp.com", "sub-1", ""))).data["grant"]

    for password in ("", "wrong-password"):
        response = _preview(
            admin_client,
            _csv(("person@corp.com", "sub-1", "")),
            confirm="true",
            grant=grant,
            password=password,
        )
        assert response.status_code == 403

    assert FederatedIdentity.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_confirming_without_a_grant_is_refused(admin_client):
    _user("person@corp.com")

    response = _preview(
        admin_client,
        _csv(("person@corp.com", "sub-1", "")),
        confirm="true",
        password=PASSWORD,
    )

    assert response.status_code == 409
    assert FederatedIdentity.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_one_bad_row_refuses_the_whole_file(admin_client):
    """All-or-nothing: the good row must not slip through with the bad one."""
    _user("person@corp.com")

    response = _preview(
        admin_client,
        _csv(("person@corp.com", "sub-1", ""), ("ghost@corp.com", "sub-2", "")),
    )

    assert response.status_code == 200
    assert response.data["valid"] is False
    assert [error["code"] for error in response.data["report"]["errors"]] == ["USER_NOT_FOUND"]
    assert response.data["report"]["errors"][0]["line"] == 3
    assert FederatedIdentity.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_an_account_that_already_signs_in_through_this_issuer_is_refused(admin_client):
    """The account-takeover shape, and the one the CLI did not check.

    A second identity at the same issuer does not replace how this account
    signs in — it adds another way, and the original keeps working, so the
    owner sees nothing.
    """
    person = _user("person@corp.com")
    FederatedIdentity.objects.create(
        user=person,
        provider="google",
        issuer=ISSUER,
        subject="the-real-subject",
        subject_format="",
        email_at_link=person.email,
        last_email=person.email,
    )

    response = _preview(admin_client, _csv(("person@corp.com", "attacker-subject", "")))

    assert response.data["valid"] is False
    assert response.data["report"]["errors"][0]["code"] == "ACCOUNT_ALREADY_FEDERATED"
    assert FederatedIdentity.objects.filter(user=person).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_two_rows_cannot_split_one_account_between_two_subjects(admin_client):
    """Same defect as above, arriving entirely within one file."""
    _user("person@corp.com")

    response = _preview(
        admin_client,
        _csv(("person@corp.com", "sub-1", ""), ("person@corp.com", "sub-2", "")),
    )

    assert response.data["valid"] is False
    assert response.data["report"]["errors"][0]["code"] == "ACCOUNT_ALREADY_FEDERATED"


@pytest.mark.contract
@pytest.mark.django_db
def test_re_importing_the_same_file_is_a_no_op(admin_client):
    """Idempotence: repeating a file must not be read as a conflict."""
    person = _user("person@corp.com")
    for _ in range(2):
        grant = _preview(admin_client, _csv(("person@corp.com", "sub-1", ""))).data["grant"]
        response = _preview(
            admin_client,
            _csv(("person@corp.com", "sub-1", "")),
            confirm="true",
            grant=grant,
            password=PASSWORD,
        )
        assert response.status_code == 200

    assert FederatedIdentity.objects.filter(user=person).count() == 1
    assert FederatedIdentityImportAudit.objects.count() == 2


@pytest.mark.contract
@pytest.mark.django_db
def test_a_subject_belonging_to_another_account_is_refused(admin_client):
    person = _user("person@corp.com")
    other = _user("other@corp.com")
    FederatedIdentity.objects.create(
        user=other,
        provider="google",
        issuer=ISSUER,
        subject="sub-1",
        subject_format="",
        email_at_link=other.email,
        last_email=other.email,
    )

    response = _preview(admin_client, _csv(("person@corp.com", "sub-1", "")))

    assert response.data["valid"] is False
    assert response.data["report"]["errors"][0]["code"] == "BINDING_OWNED_BY_ANOTHER_USER"
    assert not FederatedIdentity.objects.filter(user=person).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_file_that_is_not_a_usable_csv_is_rejected(admin_client):
    upload = io.BytesIO(b"nothing,useful\n1,2\n")
    upload.name = "wrong.csv"

    response = _preview(admin_client, upload)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid_file"


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unknown_provider_is_rejected(admin_client):
    _user("person@corp.com")

    response = admin_client.post(
        URL,
        {"file": _csv(("person@corp.com", "sub-1", "")), "provider": "nonsense", "issuer": ISSUER},
        format="multipart",
    )

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_another_admins_grant_cannot_be_used(admin_client, setup_instance):
    """A grant names the admin it was issued to."""
    _user("person@corp.com")
    grant = _preview(admin_client, _csv(("person@corp.com", "sub-1", ""))).data["grant"]

    second = _user("second@ops.example", password=PASSWORD)
    InstanceAdmin.objects.create(instance=setup_instance, user=second, role=20)
    other_client = APIClient()
    authenticate_admin(other_client, second)

    response = _preview(
        other_client,
        _csv(("person@corp.com", "sub-1", "")),
        confirm="true",
        grant=grant,
        password=PASSWORD,
    )

    assert response.status_code == 409
    assert FederatedIdentity.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_refusals_never_render_the_exception_that_caused_them(admin_client):
    """The response text is chosen from a table, never inherited from an error.

    Decoding failures chain from a library exception, so rendering the refusal
    would carry that exception's text — and whatever a future `raise ... from`
    interpolates into it — out to the caller. Every message the endpoint emits
    must therefore be one of the known constants.
    """
    latin1 = io.BytesIO("email,subject,subject_format\nkröger@corp.com,s,\n".encode("latin-1"))
    latin1.name = "mappings.csv"

    response = _preview(admin_client, latin1)

    assert response.status_code == 400
    # The chained UnicodeDecodeError names its codec and the offending byte
    # offset. Neither can appear here, because the message was not built from
    # the exception at all.
    assert response.data["error"]["message"] in REFUSAL_MESSAGES.values()
