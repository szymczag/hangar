# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The half-authenticated state between a correct password and a second factor.

Deliberately not a logged-in session. The password step never calls
``user_login()``, so ``request.user`` stays anonymous and every panel endpoint
refuses by construction rather than by a check someone must remember to write.
The blob below only records *which* administrator proved a password and how
long ago.

``InstanceAdminPermission`` additionally requires a completion marker, so even a
session created by some future code path counts as unverified until a second
factor is presented.
"""

# Python imports
from datetime import timedelta

# Django imports
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

PENDING_KEY = "admin_2fa_pending"
VERIFIED_AT_KEY = "admin_2fa_verified_at"
CREDENTIAL_KEY = "admin_2fa_credential_id"

STAGE_ASSERT = "assert"
STAGE_ENROLL = "enroll"


class PendingError(Exception):
    """Why a pending state cannot be used, as an error code."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def start(request, user, stage):
    """Record a password-verified sign-in awaiting its second factor."""
    # flush(), not cycle_key(): cycle_key keeps the session contents, so a
    # previously signed-in administrator's _auth_user_id and verification
    # marker would survive underneath this blob — and reappear the moment the
    # pending state expired and was cleared. Start genuinely empty.
    request.session.flush()
    request.session[PENDING_KEY] = {
        "user_id": str(user.id),
        "email": user.email,
        "stage": stage,
        "started_at": timezone.now().isoformat(),
        "attempts": 0,
    }
    request.session.save()


def peek(request):
    """The raw pending blob, without validating it. For status reporting."""
    blob = request.session.get(PENDING_KEY)
    return blob if isinstance(blob, dict) else None


def _window_for(stage):
    seconds = (
        settings.ADMIN_2FA_PENDING_ENROLL_WINDOW if stage == STAGE_ENROLL else settings.ADMIN_2FA_PENDING_ASSERT_WINDOW
    )
    return timedelta(seconds=seconds)


def load(request, expected_stage=None):
    """Return the pending user, or raise PendingError.

    Centralises expiry, attempt and stage checks so no endpoint can forget one.
    """
    from plane.db.models import User

    blob = peek(request)
    if not blob:
        raise PendingError("ADMIN_2FA_SESSION_EXPIRED")

    stage = blob.get("stage")
    if expected_stage is not None and stage != expected_stage:
        raise PendingError("ADMIN_2FA_SESSION_EXPIRED")

    started = parse_datetime(blob.get("started_at") or "")
    if started is None or timezone.now() - started > _window_for(stage):
        clear(request)
        raise PendingError("ADMIN_2FA_SESSION_EXPIRED")

    if int(blob.get("attempts") or 0) >= settings.ADMIN_2FA_MAX_ATTEMPTS:
        clear(request)
        raise PendingError("ADMIN_2FA_ATTEMPTS_EXHAUSTED")

    user = User.objects.filter(pk=blob.get("user_id"), is_active=True, is_bot=False).first()
    if user is None:
        clear(request)
        raise PendingError("ADMIN_2FA_SESSION_EXPIRED")
    return user, blob


def record_attempt(request):
    """Count one failed attempt against the pending state."""
    blob = peek(request)
    if not blob:
        return
    blob["attempts"] = int(blob.get("attempts") or 0) + 1
    request.session[PENDING_KEY] = blob
    request.session.save()


def clear(request):
    request.session.pop(PENDING_KEY, None)
    request.session.save()


def mark_verified(request, credential_id=None):
    """Promote the session: the second factor has been presented."""
    request.session[VERIFIED_AT_KEY] = timezone.now().isoformat()
    if credential_id is not None:
        request.session[CREDENTIAL_KEY] = str(credential_id)
    request.session.pop(PENDING_KEY, None)
    request.session.save()


def is_verified(session):
    """Whether this session completed a second factor.

    The marker's presence is what matters; its age is only checked when the
    session does not roll. With SESSION_SAVE_EVERY_REQUEST the cookie is
    refreshed on every request, so an absolute deadline measured from
    verification would cut an actively working administrator off at exactly
    ADMIN_SESSION_COOKIE_AGE while their session was still perfectly valid —
    and with no pending state to drive the second-factor page. In that
    configuration the session expiry is already the bound.
    """
    if not getattr(settings, "ADMIN_WEBAUTHN_REQUIRED", True):
        return True
    if session.get(PENDING_KEY):
        return False
    marked = parse_datetime(session.get(VERIFIED_AT_KEY) or "")
    if marked is None:
        return False
    if getattr(settings, "SESSION_SAVE_EVERY_REQUEST", False):
        return True
    return timezone.now() - marked <= timedelta(seconds=settings.ADMIN_SESSION_COOKIE_AGE)
