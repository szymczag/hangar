# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Mint a signed-in session for a user, without going through sign-in.

Two callers need this and they must agree: the test suite, which asserts what a
console session has to contain before an endpoint will accept it, and the visual
fixture seed, which hands a browser a cookie. Kept apart, the seed's idea of a
session would drift from the one the tests validate, and the day
``VERIFIED_AT_KEY`` changes shape it would be found through a screenshot.

Nothing here is reachable from a request path; it exists for fixtures.
"""

from importlib import import_module

from django.conf import settings
from django.utils import timezone

from plane.ext.auth.webauthn import pending


def _store():
    return import_module(settings.SESSION_ENGINE).SessionStore()


def mint_app_session(user) -> str:
    """A session for the application, as an ordinary sign-in would leave it."""
    session = _store()
    session["_auth_user_id"] = str(user.id)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    session.save()
    return session.session_key


def mint_admin_session(user, *, verified: bool = True) -> str:
    """A session for the instance console.

    ``verified=False`` produces the half-authenticated state -- a real session
    that has not presented a second factor, which every console endpoint must
    still refuse. That is what the test suite uses it for; a fixture wanting to
    reach the console needs ``verified=True``.
    """
    session = _store()
    session["_auth_user_id"] = str(user.id)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    if verified:
        session[pending.VERIFIED_AT_KEY] = timezone.now().isoformat()
    session.save()
    return session.session_key


__all__ = ["mint_admin_session", "mint_app_session"]
