# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Pin email domains to the identity providers allowed to assert them.

Without this policy every enabled authentication method is an equally valid
route to any address. An instance that federates ``corp.com`` through Google
Workspace still accepts a magic-code or password signup for
``someone@corp.com``, so an attacker who reaches the instance first can claim a
corporate address before its real owner ever signs in, and inherit any
invitation waiting for it.

Listing a domain here makes exactly one set of providers authoritative for it.
Every other provider is refused for that domain on both signup and login, which
is what makes a rogue IdP asserting the same addresses useless: the assertion is
only honoured when it arrives from the provider the operator designated.
"""

# Python imports
import os

# Module imports
from plane.license.utils.instance_value import get_configuration_value

# Providers that federate identity to an external directory. A bare domain
# entry (no explicit provider) admits any of these and refuses everything else.
FEDERATED_PROVIDERS = frozenset({"google", "oidc", "saml"})

# Providers that prove control of a mailbox or a password rather than directory
# membership. These are never implied by a bare domain entry; an operator who
# wants one has to name it explicitly.
CREDENTIAL_PROVIDERS = frozenset({"email", "magic-code"})

ALL_PROVIDERS = FEDERATED_PROVIDERS | CREDENTIAL_PROVIDERS | frozenset({"github", "gitlab", "gitea"})


def _normalize_domain(domain):
    """Fold a domain to its canonical ASCII form, or return "" if unusable."""
    domain = (domain or "").strip().lower().rstrip(".")
    if not domain or "@" in domain or "/" in domain:
        return ""
    try:
        return domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return ""


def parse_enforced_domains(raw):
    """Parse the ``SSO_ENFORCED_DOMAINS`` setting into {domain: {providers}}.

    Accepts comma-separated entries of either form::

        corp.com            -> any federated provider, no credentials
        corp.com=google     -> Google only
        corp.com=oidc;saml  -> either of the two named providers

    Unparseable entries and unknown provider names are dropped rather than
    raising: a typo in one entry must not disable enforcement for the others.
    An entry naming only unknown providers collapses to an empty set, which
    denies every provider for that domain — failing closed.
    """
    policy = {}
    for entry in str(raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        domain, separator, providers = entry.partition("=")
        domain = _normalize_domain(domain)
        if not domain:
            continue
        if not separator:
            policy[domain] = set(FEDERATED_PROVIDERS)
            continue
        named = {p.strip().lower() for p in providers.split(";") if p.strip()}
        policy[domain] = named & ALL_PROVIDERS
    return policy


def allowed_providers_for_email(email, raw_setting=None):
    """Return the providers permitted for ``email``, or None if unrestricted.

    None means no policy covers the address and the caller should apply its
    normal rules. An empty set means the domain is pinned but every provider
    was denied, which callers must treat as a refusal.
    """
    if raw_setting is None:
        (raw_setting,) = get_configuration_value(
            [
                {
                    "key": "SSO_ENFORCED_DOMAINS",
                    "default": os.environ.get("SSO_ENFORCED_DOMAINS", ""),
                }
            ]
        )

    policy = parse_enforced_domains(raw_setting)
    if not policy:
        return None

    _, separator, domain = str(email or "").rpartition("@")
    if not separator:
        return None
    domain = _normalize_domain(domain)
    if not domain:
        return None

    return policy.get(domain)
