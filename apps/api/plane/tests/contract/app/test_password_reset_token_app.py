# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The emailed reset link is the only thing standing between an inbox and an account.

Both reset endpoints -- the app's `/auth/reset-password/<uidb64>/<token>/` and the
public space's `/auth/spaces/reset-password/<uidb64>/<token>/` -- trust Django's
PasswordResetTokenGenerator to decide whether the link is still good. That trust
rests on three properties of the token, and nothing else in the codebase checks
them:

* it stops working once it has been used, because the password hash it was
  derived from has changed;
* it stops working after PASSWORD_RESET_TIMEOUT;
* it is bound to one account, so it cannot be replayed against another uid.

Neither endpoint answers with a 4xx. Every outcome is a redirect to the front
end, and a refusal carries `error_code` in the query string, so that is what
these assert -- together with the password itself, which is the property that
actually matters.
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.test import Client
from django.utils.encoding import smart_bytes
from django.utils.http import urlsafe_base64_encode

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.db.models import User

ORIGINAL = "original-Passw0rd-that-is-long"
NEW = "Tr0ub4dor&3-quite-long-reset"
OTHER = "c0rrect-horse-battery-Staple!"
INVALID_TOKEN = str(AUTHENTICATION_ERROR_CODES["INVALID_PASSWORD_TOKEN"])

ENDPOINTS = {
    "app": "/auth/reset-password/{uidb64}/{token}/",
    "space": "/auth/spaces/reset-password/{uidb64}/{token}/",
}


@pytest.fixture(params=sorted(ENDPOINTS))
def reset_url(request):
    return ENDPOINTS[request.param]


def _user(email):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    user.set_password(ORIGINAL)
    user.save()
    return user


def _uid(user):
    return urlsafe_base64_encode(smart_bytes(user.id))


def _post(reset_url, uidb64, token, password):
    return Client().post(reset_url.format(uidb64=uidb64, token=token), {"password": password})


def _error_code(response):
    assert response.status_code == 302, response
    return parse_qs(urlsplit(response["Location"]).query).get("error_code", [None])[0]


def _token_minted(user, seconds_ago):
    minted_at = datetime.now() - timedelta(seconds=seconds_ago)
    with patch.object(PasswordResetTokenGenerator, "_now", return_value=minted_at):
        return PasswordResetTokenGenerator().make_token(user)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_valid_token_resets_the_password(reset_url):
    user = _user("reset@example.com")
    token = PasswordResetTokenGenerator().make_token(user)

    response = _post(reset_url, _uid(user), token, NEW)

    assert _error_code(response) is None
    user.refresh_from_db()
    assert user.check_password(NEW)
    assert user.is_password_autoset is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_cannot_be_used_twice(reset_url):
    user = _user("reuse@example.com")
    uidb64 = _uid(user)
    token = PasswordResetTokenGenerator().make_token(user)
    assert _error_code(_post(reset_url, uidb64, token, NEW)) is None

    replay = _post(reset_url, uidb64, token, OTHER)

    assert _error_code(replay) == INVALID_TOKEN
    user.refresh_from_db()
    assert user.check_password(NEW), "a used reset link set the password a second time"
    assert not user.check_password(OTHER)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_older_than_the_reset_timeout_is_rejected(reset_url):
    assert settings.PASSWORD_RESET_TIMEOUT == 3600
    user = _user("expired@example.com")
    token = _token_minted(user, seconds_ago=settings.PASSWORD_RESET_TIMEOUT + 60)

    response = _post(reset_url, _uid(user), token, NEW)

    assert _error_code(response) == INVALID_TOKEN
    user.refresh_from_db()
    assert user.check_password(ORIGINAL), "an expired reset link changed the password"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_inside_the_reset_timeout_still_works(reset_url):
    """Guards the expiry test: the backdating alone must not be what rejects it."""
    user = _user("fresh@example.com")
    token = _token_minted(user, seconds_ago=settings.PASSWORD_RESET_TIMEOUT - 60)

    response = _post(reset_url, _uid(user), token, NEW)

    assert _error_code(response) is None
    user.refresh_from_db()
    assert user.check_password(NEW)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_token_for_one_account_does_not_reset_another(reset_url):
    owner = _user("owner@example.com")
    victim = _user("victim@example.com")
    token = PasswordResetTokenGenerator().make_token(owner)

    response = _post(reset_url, _uid(victim), token, NEW)

    assert _error_code(response) == INVALID_TOKEN
    victim.refresh_from_db()
    owner.refresh_from_db()
    assert victim.check_password(ORIGINAL), "another account's reset link changed this password"
    assert owner.check_password(ORIGINAL)
