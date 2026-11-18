# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""One rule for every path that gives an account a password.

An account bound to an identity provider has no Hangar password, and must not
be able to obtain one. A local password is a way out from under the provider:
the instance would then accept a password for an identity the administrator
pinned to SSO, and the provider's own controls -- its second factor, its
lockout, its deprovisioning -- would stop being the only way in.

Changing, setting and resetting a password all ask this module, so the
condition and the wording cannot drift between them.
"""

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)

FEDERATED_PASSWORD_MESSAGE = (
    "This account signs in through an identity provider and has no Hangar "
    "password. Change it with your provider instead."
)


def is_password_managed_by_provider(user) -> bool:
    """Return whether the account is bound to an identity provider."""
    return user.federated_identities.exists()


def federated_password_exception() -> AuthenticationException:
    return AuthenticationException(
        error_code=AUTHENTICATION_ERROR_CODES["PASSWORD_MANAGED_BY_IDENTITY_PROVIDER"],
        error_message="PASSWORD_MANAGED_BY_IDENTITY_PROVIDER",
        payload={"error": FEDERATED_PASSWORD_MESSAGE},
    )


def federated_password_refusal() -> Response:
    """The API answer for a signed-in account asking for a password it cannot have."""
    return Response(federated_password_exception().get_error_dict(), status=status.HTTP_403_FORBIDDEN)
