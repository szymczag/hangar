# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Error codes for fork authentication providers (OIDC, SAML).
#
# Kept in a separate registry so plane/authentication/adapter/error.py stays
# untouched (see FORK.md). The 53xx block is unused by upstream; verify that
# still holds after every upstream sync.

EXT_AUTHENTICATION_ERROR_CODES = {
    # OIDC
    "OIDC_NOT_CONFIGURED": 5300,
    "OIDC_PROVIDER_ERROR": 5301,
    "OIDC_TOKEN_VALIDATION_FAILED": 5302,
    "OIDC_UNVERIFIED_EMAIL": 5303,
    # SAML
    "SAML_NOT_CONFIGURED": 5310,
    "SAML_PROVIDER_ERROR": 5311,
    "INVALID_SAML_RESPONSE": 5312,
}
