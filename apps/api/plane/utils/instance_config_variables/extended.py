# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Fork configuration variables (see FORK.md). This module is upstream's
# designated extension hook — upstream ships it as an empty list.

# Python imports
import os

# Enable OIDC automatically when the environment carries a full configuration,
# mirroring how upstream derives its IS_<PROVIDER>_ENABLED flags. An explicit
# IS_OIDC_ENABLED env var always wins; the admin UI can toggle it afterwards.
_oidc_env_configured = all(bool(os.environ.get(key)) for key in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"))

oidc_config_variables = [
    {
        "key": "IS_OIDC_ENABLED",
        "value": os.environ.get("IS_OIDC_ENABLED", "1" if _oidc_env_configured else "0"),
        "category": "OIDC",
        "is_encrypted": False,
    },
    {
        "key": "OIDC_ISSUER",
        "value": os.environ.get("OIDC_ISSUER"),
        "category": "OIDC",
        "is_encrypted": False,
    },
    {
        "key": "OIDC_CLIENT_ID",
        "value": os.environ.get("OIDC_CLIENT_ID"),
        "category": "OIDC",
        "is_encrypted": False,
    },
    {
        "key": "OIDC_CLIENT_SECRET",
        "value": os.environ.get("OIDC_CLIENT_SECRET"),
        "category": "OIDC",
        "is_encrypted": True,
    },
    {
        "key": "OIDC_PROVIDER_NAME",
        "value": os.environ.get("OIDC_PROVIDER_NAME", "OIDC"),
        "category": "OIDC",
        "is_encrypted": False,
    },
]

# Same env-derived enablement pattern as OIDC.
_saml_env_configured = all(
    bool(os.environ.get(key)) for key in ("SAML_IDP_ENTITY_ID", "SAML_IDP_SSO_URL", "SAML_IDP_CERTIFICATE")
)

saml_config_variables = [
    {
        "key": "IS_SAML_ENABLED",
        "value": os.environ.get("IS_SAML_ENABLED", "1" if _saml_env_configured else "0"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_PROVIDER_NAME",
        "value": os.environ.get("SAML_PROVIDER_NAME", "SAML"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_IDP_ENTITY_ID",
        "value": os.environ.get("SAML_IDP_ENTITY_ID"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_IDP_SSO_URL",
        "value": os.environ.get("SAML_IDP_SSO_URL"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        # The IdP's public signing certificate (PEM) — public key material,
        # stored unencrypted.
        "key": "SAML_IDP_CERTIFICATE",
        "value": os.environ.get("SAML_IDP_CERTIFICATE"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_ATTR_EMAIL",
        "value": os.environ.get("SAML_ATTR_EMAIL"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_ATTR_FIRST_NAME",
        "value": os.environ.get("SAML_ATTR_FIRST_NAME"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_ATTR_LAST_NAME",
        "value": os.environ.get("SAML_ATTR_LAST_NAME"),
        "category": "SAML",
        "is_encrypted": False,
    },
    {
        "key": "SAML_ATTR_SUBJECT",
        "value": os.environ.get("SAML_ATTR_SUBJECT"),
        "category": "SAML",
        "is_encrypted": False,
    },
]

# Domains whose identity is owned by a designated provider. Comma-separated
# entries of "domain", "domain=provider", or "domain=provider1;provider2".
# A bare domain admits any federated provider (google, oidc, saml) and refuses
# password and magic-code sign-in for that domain.
sso_policy_config_variables = [
    {
        "key": "SSO_ENFORCED_DOMAINS",
        "value": os.environ.get("SSO_ENFORCED_DOMAINS", ""),
        "category": "SSO",
        "is_encrypted": False,
    },
    # Workspaces a federated user joins on sign-in, as
    # "domain=workspace-slug:role" entries. Only applies to domains that
    # SSO_ENFORCED_DOMAINS pins to a provider.
    {
        "key": "SSO_AUTO_JOIN_WORKSPACES",
        "value": os.environ.get("SSO_AUTO_JOIN_WORKSPACES", ""),
        "category": "SSO",
        "is_encrypted": False,
    },
    # Projects a federated user joins on sign-in, as
    # "domain=workspace-slug/IDENTIFIER:role" entries. Requires the matching
    # workspace membership, so it is normally paired with the setting above.
    {
        "key": "SSO_AUTO_JOIN_PROJECTS",
        "value": os.environ.get("SSO_AUTO_JOIN_PROJECTS", ""),
        "category": "SSO",
        "is_encrypted": False,
    },
]

extended_config_variables = [*oidc_config_variables, *saml_config_variables, *sso_policy_config_variables]
