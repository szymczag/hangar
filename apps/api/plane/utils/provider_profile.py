# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Which identity providers own the name and picture of the accounts they admit.

Where attribute sync is enabled, `Adapter.sync_user_data` rewrites first name,
last name and display name on every sign-in and replaces the avatar, deleting any
uploaded file first. Three separate places need to know this: the adapter that
performs the sync, the instance endpoint that tells the clients not to offer an
edit that will be discarded, and the sign-in workflow, which must not send
somebody to a screen that asks for a name the provider is about to supply.

They read it from here so the three cannot disagree.
"""

import os

from plane.license.utils.instance_value import get_configuration_value

PROVIDER_SYNC_KEYS = {
    "google": "ENABLE_GOOGLE_SYNC",
    "github": "ENABLE_GITHUB_SYNC",
    "gitlab": "ENABLE_GITLAB_SYNC",
    "gitea": "ENABLE_GITEA_SYNC",
}


def providers_managing_profiles() -> list[str]:
    """Providers whose accounts have their profile written for them."""
    values = get_configuration_value(
        [{"key": key, "default": os.environ.get(key, "0")} for key in PROVIDER_SYNC_KEYS.values()]
    )
    return [provider for provider, value in zip(PROVIDER_SYNC_KEYS, values, strict=False) if str(value) == "1"]


def provider_manages_profile(provider: str | None) -> bool:
    """Whether this provider writes the profile of the accounts it admits."""
    key = PROVIDER_SYNC_KEYS.get(provider or "")
    if not key:
        return False
    (enabled,) = get_configuration_value([{"key": key, "default": os.environ.get(key, "0")}])
    return str(enabled) == "1"
