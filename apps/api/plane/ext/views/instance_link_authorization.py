# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Authorising existing accounts to be linked on their next SSO sign-in.

The supported way to attach an existing account to a provider identity is to
import that person's subject — for Google, the `sub` claim from the Admin SDK.
An operator holding only a list of addresses has no way to produce that, and
every one of those people is refused at sign-in.

This accepts the addresses instead. It does not link anything: it records that
the next assertion from a named issuer for that address may bind whatever
subject it carries, which means the subject is taken from the assertion rather
than guessed in advance. What makes that safe enough to offer is checked at
sign-in — see plane.ext.services.federated_link — and what makes it accountable
is here: the console's second factor, the administrator's password at the point
of use, and a record of who authorised what.
"""

# Python imports
from datetime import timedelta

# Django imports
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.authentication.session import BaseSessionAuthentication
from plane.authentication.utils.sso_domain_policy import allowed_providers_for_email
from plane.db.models import FederatedIdentity, User
from plane.ext.models import FederatedLinkAuthorization
from plane.license.api.permissions import InstanceAdminPermission

# Long enough for people to be told and to sign in; short enough that a list
# nobody acted on stops being spendable.
DEFAULT_VALIDITY_DAYS = 14
MAX_ADDRESSES = 500


def _error(message: str, response_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": message}, status=response_status)


def _classify(address: str, provider: str, issuer: str) -> tuple[str, str]:
    """Return (state, explanation) for one address, without writing anything."""
    user = User.objects.filter(email__iexact=address, is_bot=False).first()
    if user is None:
        return "no-account", "No account on this instance uses this address."

    allowed = allowed_providers_for_email(address)
    if not allowed or provider not in allowed:
        return (
            "domain-not-pinned",
            "This domain is not pinned to this provider, so an assertion about it proves nothing.",
        )

    if FederatedIdentity.objects.filter(user=user, provider=provider, issuer=issuer).exists():
        return "already-linked", "This account already signs in through this provider."

    return "will-link", "Will be linked on the next sign-in through this provider."


class InstanceLinkAuthorizationEndpoint(BaseAPIView):
    """Preview a list of addresses, then authorise the ones that can be linked."""

    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        """What is currently authorised and still spendable."""
        pending = FederatedLinkAuthorization.objects.filter(
            consumed_at__isnull=True, expires_at__gt=timezone.now()
        ).order_by("email")
        return Response(
            {
                "authorizations": [
                    {
                        "email": row.email,
                        "provider": row.provider,
                        "issuer": row.issuer,
                        "expires_at": row.expires_at,
                    }
                    for row in pending
                ]
            },
            status=status.HTTP_200_OK,
        )

    @method_decorator(csrf_protect)
    def post(self, request):
        provider = (request.data.get("provider") or "").strip().lower()
        issuer = (request.data.get("issuer") or "").strip()
        note = (request.data.get("note") or "").strip()
        raw = request.data.get("emails") or ""

        if not provider or not issuer:
            return _error("Choose the provider and issuer these accounts will sign in through.")

        addresses, malformed = [], []
        for line in str(raw).replace(",", "\n").splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                validate_email(candidate)
            except DjangoValidationError:
                malformed.append(candidate[:64])
                continue
            cleaned = candidate.lower()
            if cleaned not in addresses:
                addresses.append(cleaned)

        if malformed:
            return _error(f"These are not email addresses: {', '.join(malformed[:5])}")
        if not addresses:
            return _error("Paste at least one email address.")
        if len(addresses) > MAX_ADDRESSES:
            return _error(f"Authorise at most {MAX_ADDRESSES} addresses at a time.")

        rows = [
            {"email": address, "state": state, "detail": detail}
            for address in addresses
            for state, detail in [_classify(address, provider, issuer)]
        ]

        if str(request.data.get("confirm") or "").lower() != "true":
            return Response({"rows": rows}, status=status.HTTP_200_OK)

        password = request.data.get("password") or ""
        if not password or not request.user.check_password(password):
            return _error(
                "Re-enter your password to authorise account linking.",
                status.HTTP_403_FORBIDDEN,
            )

        linkable = [row["email"] for row in rows if row["state"] == "will-link"]
        if not linkable:
            return _error("None of these addresses can be linked; see the preview.", status.HTTP_409_CONFLICT)

        expires_at = timezone.now() + timedelta(days=DEFAULT_VALIDITY_DAYS)
        # Existing unspent authorisations for the same address are left alone:
        # one is enough, and replacing them would reset an expiry an
        # administrator may have been counting on.
        already = set(
            FederatedLinkAuthorization.objects.filter(
                email__in=linkable,
                provider=provider,
                issuer=issuer,
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).values_list("email", flat=True)
        )
        created = [
            FederatedLinkAuthorization(
                email=address,
                provider=provider,
                issuer=issuer,
                authorized_by=request.user,
                note=note,
                expires_at=expires_at,
            )
            for address in linkable
            if address not in already
        ]
        FederatedLinkAuthorization.objects.bulk_create(created)

        return Response(
            {"rows": rows, "authorized": len(created), "expires_at": expires_at},
            status=status.HTTP_200_OK,
        )
