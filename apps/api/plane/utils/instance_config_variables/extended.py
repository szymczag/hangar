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
_oidc_env_configured = all(
    bool(os.environ.get(key)) for key in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET")
)

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
    {
        "key": "OIDC_ALLOW_UNVERIFIED_EMAIL",
        "value": os.environ.get("OIDC_ALLOW_UNVERIFIED_EMAIL", "0"),
        "category": "OIDC",
        "is_encrypted": False,
    },
]

extended_config_variables = oidc_config_variables
