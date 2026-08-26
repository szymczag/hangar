# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Deciding whether an existing account may be linked to an asserted identity.

Sign-in refuses to link an account by email, because an address is not proof of
anything: whoever controls a mailbox, or a provider willing to assert any
address, would otherwise take over accounts. That rule is right, and it leaves
an operator holding a list of colleagues who cannot sign in.

An authorization relaxes it for one address, once. The relaxation is only
defensible because of what is checked alongside it, and all of it is checked
here rather than at the call site, so there is one place to read:

1. an administrator authorised this exact address for this exact issuer, the
   authorisation has not been spent, and it has not expired;
2. the address's domain is **pinned to this provider**, so the identity provider
   is the authority for that domain rather than whoever typed the address;
3. the provider asserted the address as verified — the sign-in path refuses
   unverified addresses before reaching here, and this does not undo that;
4. the account has no identity at this issuer already, which would mean the
   person can sign in and something else is wrong.

Failing any of them leaves the original refusal in place.
"""

# Django imports
from django.db import transaction
from django.utils import timezone

# Module imports
from plane.authentication.utils.sso_domain_policy import allowed_providers_for_email
from plane.db.models import FederatedIdentity
from plane.ext.models import FederatedLinkAudit, FederatedLinkAuthorization


def _pinned_to(email: str, provider: str) -> bool:
    """Whether the address's domain is pinned to this provider.

    An unpinned domain means anyone could have registered the address, so an
    assertion about it says nothing about who owns the account. `None` from the
    policy means "not listed", which is exactly that case.
    """
    allowed = allowed_providers_for_email(email)
    return bool(allowed) and provider in allowed


def claim_authorization(*, email: str, provider: str, issuer: str, subject: str, user):
    """Spend an authorization for this sign-in, or return None.

    Returns the consumed row so the caller can tell that linking was permitted;
    the caller creates the identity, because that belongs in the same
    transaction as the rest of the sign-in.
    """
    address = (email or "").strip().lower()
    if not address or not provider or not issuer or not subject:
        return None

    if not _pinned_to(address, provider):
        return None

    if FederatedIdentity.objects.filter(user=user, provider=provider, issuer=issuer).exists():
        return None

    now = timezone.now()
    with transaction.atomic():
        # Locked and re-checked: two sign-ins racing must not both spend it.
        authorization = (
            FederatedLinkAuthorization.objects.select_for_update()
            .filter(
                email__iexact=address,
                provider=provider,
                issuer=issuer,
                consumed_at__isnull=True,
                expires_at__gt=now,
            )
            .order_by("created_at")
            .first()
        )
        if authorization is None:
            return None

        authorization.consumed_at = now
        authorization.consumed_subject = subject
        authorization.consumed_by = user
        authorization.save(update_fields=["consumed_at", "consumed_subject", "consumed_by", "updated_at"])

        FederatedLinkAudit.objects.create(
            email=address,
            provider=provider,
            issuer=issuer,
            subject=subject,
            user=user,
            authorized_by=authorization.authorized_by,
            authorized_at=authorization.created_at,
            note=authorization.note,
        )

    return authorization
