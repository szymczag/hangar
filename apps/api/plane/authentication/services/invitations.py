# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.utils import timezone

from plane.db.models import WorkspaceMemberInvite


def active_signup_invitations(email, *, for_update=False, now=None):
    """Pending invitations that may authorize one closed-registration signup."""
    now = now or timezone.now()
    queryset = WorkspaceMemberInvite.objects.filter(
        email__iexact=email,
        accepted=False,
        responded_at__isnull=True,
        revoked_at__isnull=True,
        consumed_at__isnull=True,
        signup_authorized_at__isnull=True,
        deleted_at__isnull=True,
    ).filter(expires_at__gt=now)
    return queryset.select_for_update() if for_update else queryset


def accepted_membership_invitations(email, *, for_update=False, now=None):
    """Accepted invitations that may grant membership exactly once."""
    now = now or timezone.now()
    queryset = WorkspaceMemberInvite.objects.filter(
        email__iexact=email,
        accepted=True,
        responded_at__isnull=False,
        revoked_at__isnull=True,
        consumed_at__isnull=True,
        deleted_at__isnull=True,
        expires_at__gt=now,
    )
    return queryset.select_for_update() if for_update else queryset
