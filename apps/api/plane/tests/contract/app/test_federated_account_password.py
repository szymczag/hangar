# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An account that signs in through a provider has no Hangar password to set.

`is_password_autoset` is true for such an account, and the change-password
endpoint read that as "no old password to confirm" and let the request through.
So an account the administrator pinned to SSO could give itself a Hangar
password, and from then on the provider's own controls -- its second factor, its
lockout, its deprovisioning -- were no longer the only way in.

The refusal is the same shape as the one on the address, in
`test_federated_account_email_change.py`, and for the same underlying reason: the
provider owns this account, so the parts of it the provider governs are not
editable here.

Changing a password is one of four ways to obtain one. Setting a first password
(the onboarding step) and the emailed reset link -- app and public space -- must
refuse the same accounts, or the change-password refusal only moves the door.
"""

import uuid
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from django.utils.encoding import smart_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.db.models import FederatedIdentity, Profile, User
from plane.license.models import Instance

ISSUER = "https://accounts.google.com"
CHANGE_URL = "/auth/change-password/"
SET_URL = "/auth/set-password/"
FORGOT_URLS = ["/auth/forgot-password/", "/auth/spaces/forgot-password/"]
RESET_URLS = [
    "/auth/reset-password/{uidb64}/{token}/",
    "/auth/spaces/reset-password/{uidb64}/{token}/",
]
STRONG = "Tr0ub4dor&3-quite-long"
REFUSED = str(AUTHENTICATION_ERROR_CODES["PASSWORD_MANAGED_BY_IDENTITY_PROVIDER"])


@pytest.fixture(autouse=True)
def _fresh_cache():
    # The auth throttle counts in the cache; a test must not inherit another's.
    cache.clear()
    yield
    cache.clear()


def _link(user):
    FederatedIdentity.objects.create(
        user=user,
        provider="google",
        issuer=ISSUER,
        subject=uuid.uuid4().hex,
        subject_format="",
        email_at_link=user.email,
        last_email=user.email,
    )


def _account(email, federated):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    if federated:
        # What federated_auth.py writes when it creates the account, and the
        # whole reason this was reachable: it is what tells the endpoint there
        # is no old password to confirm.
        user.is_password_autoset = True
        user.set_unusable_password()
        user.save()
        _link(user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_cannot_set_a_password():
    client, user = _account("person@corp.com", federated=True)

    response = client.post(CHANGE_URL, {"new_password": STRONG}, format="json")

    assert response.status_code == 403
    user.refresh_from_db()
    assert not user.check_password(STRONG), "the provider-owned account was given a Hangar password"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_refusal_says_where_to_go_instead():
    """A 403 with no explanation reads as a bug in the console."""
    client, _user = _account("person@corp.com", federated=True)

    response = client.post(CHANGE_URL, {"new_password": STRONG}, format="json")

    assert "identity provider" in str(response.data).lower()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_cannot_set_one_by_supplying_an_old_password():
    """The guard must not depend on which fields the request happens to carry."""
    client, user = _account("person@corp.com", federated=True)

    response = client.post(CHANGE_URL, {"old_password": "anything", "new_password": STRONG}, format="json")

    assert response.status_code == 403
    user.refresh_from_db()
    assert not user.check_password(STRONG)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_ordinary_account_can_still_set_one():
    """The guard is about who owns the account, not about passwords in general."""
    client, user = _account("person@example.com", federated=False)
    user.set_password("OldPassw0rd!-long-enough")
    user.is_password_autoset = False
    user.save()

    response = client.post(
        CHANGE_URL,
        {"old_password": "OldPassw0rd!-long-enough", "new_password": STRONG},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(STRONG)


# -- Setting a first password ------------------------------------------------


def _autoset_account(email, federated):
    """The state onboarding offers a password to: one was never chosen."""
    client, user = _account(email, federated=federated)
    if not federated:
        user.is_password_autoset = True
        user.set_password(uuid.uuid4().hex)
        user.save()
    return client, user


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_cannot_set_a_first_password():
    client, user = _autoset_account("person@corp.com", federated=True)

    response = client.post(SET_URL, {"password": STRONG}, format="json")

    assert response.status_code == 403
    assert str(response.data["error_code"]) == REFUSED
    assert "identity provider" in str(response.data).lower()
    user.refresh_from_db()
    assert not user.check_password(STRONG), "the provider-owned account was given a Hangar password"
    assert user.is_password_autoset is True


@pytest.mark.contract
@pytest.mark.django_db
def test_change_and_set_refuse_with_the_same_answer():
    """One helper decides both, so the two refusals cannot drift apart."""
    client, _user = _autoset_account("person@corp.com", federated=True)

    changed = client.post(CHANGE_URL, {"new_password": STRONG}, format="json")
    cache.clear()
    set_ = client.post(SET_URL, {"password": STRONG}, format="json")

    assert changed.status_code == set_.status_code == 403
    assert changed.data == set_.data


@pytest.mark.contract
@pytest.mark.django_db
def test_an_ordinary_account_can_still_set_a_first_password():
    client, user = _autoset_account("person@example.com", federated=False)

    response = client.post(SET_URL, {"password": STRONG}, format="json")

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(STRONG)
    assert user.is_password_autoset is False


# -- Asking for a reset link -------------------------------------------------


@pytest.fixture
def instance(db):
    return Instance.objects.create(
        instance_name="Corp Hangar",
        instance_id=str(uuid.uuid4()),
        current_version="0.1.0-rc.99",
        domain="hangar.corp.example",
        last_checked_at=timezone.now(),
        is_setup_done=True,
    )


@pytest.fixture
def mail():
    """Both forgot-password endpoints with mail delivery on and the send captured."""
    with (
        patch("plane.authentication.views.app.password_management.is_email_delivery_configured", return_value=True),
        patch("plane.authentication.views.space.password_management.is_email_delivery_configured", return_value=True),
        patch("plane.authentication.views.app.password_management.forgot_password.delay") as app_mail,
        patch("plane.authentication.views.space.password_management.forgot_password.delay") as space_mail,
    ):
        yield lambda: app_mail.call_count + space_mail.call_count


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", FORGOT_URLS)
def test_no_reset_link_is_sent_to_a_federated_account(url, instance, mail):
    _client, user = _account("person@corp.com", federated=True)

    response = APIClient().post(url, {"email": user.email}, format="json")

    assert response.status_code == 200
    assert mail() == 0, "a reset link was issued for an account the provider owns"


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", FORGOT_URLS)
def test_the_answer_does_not_say_which_accounts_are_federated(url, instance, mail):
    """Federated, ordinary and unknown addresses all get the same reply."""
    _c, federated = _account("federated@corp.com", federated=True)
    _c, ordinary = _account("ordinary@example.com", federated=False)
    client = APIClient()

    answers = []
    for email in (federated.email, ordinary.email, "nobody-here@corp.example"):
        cache.clear()
        answers.append(client.post(url, {"email": email}, format="json"))

    assert {answer.status_code for answer in answers} == {200}
    assert answers[0].json() == answers[1].json() == answers[2].json()
    assert mail() == 1, "only the ordinary account should have been sent a link"


# -- Using a reset link -------------------------------------------------------


def _reset(url, user, token, password):
    uidb64 = urlsafe_base64_encode(smart_bytes(user.id))
    response = Client().post(url.format(uidb64=uidb64, token=token), {"password": password})
    assert response.status_code == 302, response
    return parse_qs(urlsplit(response["Location"]).query).get("error_code", [None])[0]


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", RESET_URLS)
def test_a_link_issued_before_the_identity_was_linked_is_refused(url):
    """The token is still valid -- linking an identity does not touch what it is derived from."""
    _client, user = _account("person@corp.com", federated=False)
    user.set_password("OldPassw0rd!-long-enough")
    user.save()
    token = PasswordResetTokenGenerator().make_token(user)
    _link(user)
    assert PasswordResetTokenGenerator().check_token(user, token), "the precondition this test relies on"

    error_code = _reset(url, user, token, STRONG)

    assert error_code == REFUSED
    user.refresh_from_db()
    assert not user.check_password(STRONG), "a reset link gave the provider-owned account a new password"
    assert user.check_password("OldPassw0rd!-long-enough")


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", RESET_URLS)
def test_a_federated_account_with_no_password_cannot_be_given_one_by_link(url):
    _client, user = _account("person@corp.com", federated=True)
    token = PasswordResetTokenGenerator().make_token(user)

    assert _reset(url, user, token, STRONG) == REFUSED
    user.refresh_from_db()
    assert not user.has_usable_password()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", RESET_URLS)
def test_an_invalid_link_does_not_reveal_that_the_account_is_federated(url):
    """Federation is checked after the token, so a guess learns only that the link is bad."""
    _client, user = _account("person@corp.com", federated=True)

    assert _reset(url, user, "not-a-token", STRONG) == str(AUTHENTICATION_ERROR_CODES["INVALID_PASSWORD_TOKEN"])


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", RESET_URLS)
def test_an_ordinary_account_can_still_reset(url):
    _client, user = _account("person@example.com", federated=False)
    user.set_password("OldPassw0rd!-long-enough")
    user.save()
    token = PasswordResetTokenGenerator().make_token(user)

    assert _reset(url, user, token, STRONG) is None
    user.refresh_from_db()
    assert user.check_password(STRONG)
