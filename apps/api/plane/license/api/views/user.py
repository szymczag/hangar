# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Read-only view of who exists on the instance and how they sign in.

The panel had no user list at all, so an operator could not answer "who has an
account here and where do they come from" without database access. That is the
question to answer before pinning a domain to an identity provider, because the
accounts that will be refused at the cutover are invisible in an ordinary list.

Deliberately read-only: this reports, it does not manage accounts. Anything
that mutates a user belongs behind its own review rather than arriving as a
side effect of adding a listing.
"""

# Django imports
from django.db.models import Prefetch

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.db.models import Account, FederatedIdentity, User
from plane.license.api.permissions import InstanceAdminPermission

# How an account will behave when its domain is pinned to a given provider.
STATUS_FEDERATED = "federated"
STATUS_ADOPTABLE = "adoptable"
STATUS_NEEDS_IMPORT = "needs-import"
STATUS_NO_SSO = "password-only"


def classify(user, bound_providers, oauth_providers, provider):
    """Describe how this account signs in, and what a cutover would do to it."""
    if provider:
        if provider in bound_providers:
            return STATUS_FEDERATED
        if provider in oauth_providers:
            # A prior OAuth account for the same provider is adopted on the
            # next sign-in, keeping the user id and memberships.
            return STATUS_ADOPTABLE
        # Nothing links this account to the provider, so its address is held by
        # an unlinked user and sign-in would be refused.
        return STATUS_NEEDS_IMPORT
    if bound_providers:
        return STATUS_FEDERATED
    if oauth_providers:
        return STATUS_ADOPTABLE
    return STATUS_NO_SSO


class InstanceUserEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        domain = (request.query_params.get("domain") or "").strip().lstrip("@").lower()
        provider = (request.query_params.get("provider") or "").strip().lower()
        include_inactive = request.query_params.get("include_inactive") == "true"

        if provider and provider not in dict(FederatedIdentity.Provider.choices):
            return Response(
                {"error": "Unknown provider."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = User.objects.filter(is_bot=False).prefetch_related(
            Prefetch(
                "federated_identities",
                queryset=FederatedIdentity.objects.only("user_id", "provider", "issuer", "last_authenticated_at"),
            ),
            Prefetch("accounts", queryset=Account.objects.only("user_id", "provider")),
        )
        if not include_inactive:
            users = users.filter(is_active=True)
        if domain:
            users = users.filter(email__iendswith=f"@{domain}")
        if search:
            users = users.filter(email__icontains=search)

        users = users.order_by("email")

        def on_results(results):
            payload = []
            for user in results:
                identities = list(user.federated_identities.all())
                bound_providers = sorted({identity.provider for identity in identities})
                oauth_providers = sorted({account.provider for account in user.accounts.all()})
                payload.append(
                    {
                        "id": str(user.id),
                        "email": user.email,
                        "display_name": user.display_name,
                        "is_active": user.is_active,
                        "has_password": not user.is_password_autoset,
                        "last_login_at": user.last_login_time,
                        "federated_identities": [
                            {
                                "provider": identity.provider,
                                "issuer": identity.issuer,
                                "last_authenticated_at": identity.last_authenticated_at,
                            }
                            for identity in identities
                        ],
                        "oauth_accounts": oauth_providers,
                        "status": classify(user, bound_providers, oauth_providers, provider),
                    }
                )
            return payload

        return self.paginate(
            request=request,
            queryset=users,
            on_results=on_results,
            max_per_page=50,
            default_per_page=25,
        )
