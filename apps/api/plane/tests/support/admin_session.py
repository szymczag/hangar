# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Helpers for driving the instance-admin console in tests.

Two things make the console awkward to test, and both are deliberate design:

The session middleware selects its cookie by the substring "instances" in the
request path, so the console session lives in ADMIN_SESSION_COOKIE_NAME.
Django's ``client.session`` reads SESSION_COOKIE_NAME and therefore cannot see
it — that isolation is the point, so tests reach for the right cookie.

InstanceAdminPermission requires a second-factor marker in the session, so
``force_authenticate`` alone is no longer enough to reach a console endpoint;
it installs a user without a session and thus without a marker.
"""

from importlib import import_module

from django.conf import settings
from django.utils import timezone

from plane.ext.auth.webauthn import pending


def read_admin_session(client):
    """The console session behind this client, or an empty one."""
    cookie = client.cookies.get(settings.ADMIN_SESSION_COOKIE_NAME)
    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore(cookie.value if cookie else None)


def store_admin_session(client, session):
    session.save()
    client.cookies[settings.ADMIN_SESSION_COOKIE_NAME] = session.session_key


def authenticate_admin(client, user, verified=True):
    """Give the client a console session, as a completed sign-in would.

    ``verified=False`` produces the half-authenticated state: a real session
    that has not presented a second factor, which every console endpoint must
    still refuse.
    """
    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore()
    session["_auth_user_id"] = str(user.id)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    if verified:
        session[pending.VERIFIED_AT_KEY] = timezone.now().isoformat()
    store_admin_session(client, session)
    return session


__all__ = ["authenticate_admin", "read_admin_session", "store_admin_session"]
