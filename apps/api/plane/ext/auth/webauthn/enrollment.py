# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Whether an administrator has a second factor, has none, or has lost theirs.

The answer decides what a correct password leads to, so it lives in one place.
Three states rather than a boolean: a credential disabled by clone detection
still counts as enrolled. Treating "no active key" as "never enrolled" would
hand the enrollment page to anyone who knows the password the moment the only
key was disabled — exactly when the key is suspected of being copied.

A credential removed by ``manage.py disable_instance_admin_2fa`` is soft
deleted, and the default manager does not return it, so after that reset the
administrator is back to NONE and enrolls again. That command is the only way
out of LOCKED.
"""

# Module imports
from plane.ext.models import InstanceAdminWebAuthnCredential

ACTIVE = "active"
LOCKED = "locked"
NONE = "none"

RESET_COMMAND = "disable_instance_admin_2fa"


def state_for(user):
    """ACTIVE, LOCKED (only disabled credentials) or NONE (never enrolled)."""
    credentials = InstanceAdminWebAuthnCredential.objects.filter(user=user)
    if credentials.filter(disabled_at__isnull=True).exists():
        return ACTIVE
    if credentials.exists():
        return LOCKED
    return NONE
