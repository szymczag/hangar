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


def _enforced_domains_setting(raw_setting=None):
    """The raw ``SSO_ENFORCED_DOMAINS`` value, read from the instance if absent."""
    if raw_setting is not None:
        return raw_setting
    (value,) = get_configuration_value(
        [
            {
                "key": "SSO_ENFORCED_DOMAINS",
                "default": os.environ.get("SSO_ENFORCED_DOMAINS", ""),
            }
        ]
    )
    return value


def allowed_providers_for_email(email, raw_setting=None):
    """Return the providers permitted for ``email``, or None if unrestricted.

    None means no policy covers the address and the caller should apply its
    normal rules. An empty set means the domain is pinned but every provider
    was denied, which callers must treat as a refusal.
    """
    policy = parse_enforced_domains(_enforced_domains_setting(raw_setting))
    if not policy:
        return None

    _, separator, domain = str(email or "").rpartition("@")
    if not separator:
        return None
    domain = _normalize_domain(domain)
    if not domain:
        return None

    return policy.get(domain)


def _restrict_invites_enabled(raw_setting=None):
    """Whether invitations are confined to the domains pinned above."""
    if raw_setting is None:
        (raw_setting,) = get_configuration_value(
            [
                {
                    "key": "RESTRICT_INVITES_TO_SSO_DOMAINS",
                    "default": os.environ.get("RESTRICT_INVITES_TO_SSO_DOMAINS", "0"),
                }
            ]
        )
    return str(raw_setting or "").strip() == "1"


def invitation_rejection_reason(email, *, raw_setting=None, restrict_setting=None):
    """Explain why ``email`` cannot be invited, or return None if it can.

    Enforcement has always lived at sign-in, which means an address the policy
    will refuse can still be invited: the row is written and the invitation
    email is sent, and only days later does the invitee discover the account
    cannot be created. The admin learns nothing at the moment of the mistake,
    and an outsider has meanwhile been told the workspace name and who invited
    them.

    Two of the three rules here reject only invitations that provably cannot be
    accepted, so they apply whether or not the operator confined invitations:
    a domain that denies every provider has nobody who can sign in, and a
    directory-backed domain issues no account carrying a plus tag. The
    allowlist rule is the one that expresses a choice, so it is the one behind
    the setting.
    """
    address = str(email or "").strip()
    local_part, _, _domain = address.rpartition("@")
    raw_setting = _enforced_domains_setting(raw_setting)
    allowed = allowed_providers_for_email(address, raw_setting=raw_setting)

    if allowed is None:
        # Confining invitations to a list that is empty would refuse every
        # address on the instance, which is a misconfiguration rather than an
        # intention. With nothing pinned there is nothing to confine them to.
        if _restrict_invites_enabled(restrict_setting) and parse_enforced_domains(raw_setting):
            return (
                f"{address} is outside the domains this instance federates. "
                "Invite an address on a domain named in the domain policy."
            )
        return None

    if not allowed:
        return (
            f"{address} is on a domain whose policy allows no sign-in method at all, "
            "so the invitation could not be accepted."
        )

    # A plus tag proves a mailbox, not directory membership. Google Workspace and
    # every other directory issue accounts without one, so the assertion at
    # sign-in would carry the bare address and never match this invitation.
    # Where the operator kept a credential provider for the domain, the tag can
    # still be proved, and is left alone.
    if "+" in local_part and not allowed & CREDENTIAL_PROVIDERS:
        return (
            f"{address} carries a plus tag. This domain signs in through an identity provider, "
            "which issues accounts without one, so the invitation could not be accepted."
        )

    return None


def invitation_policy_snapshot(raw_setting=None, restrict_setting=None):
    """The policy in the shape a client needs to apply the same three rules.

    The admin panel holds the settings, and only an instance admin may read
    them. An invite dialog needs no more than which domains are pinned and
    whether each accepts a plus tag, so that is all this returns — to callers
    who can already invite. The server stays authoritative: this only moves the
    refusal earlier, so an admin is not told after the round trip.
    """
    raw_setting = _enforced_domains_setting(raw_setting)
    policy = parse_enforced_domains(raw_setting)
    return {
        "restrict_to_domains": bool(_restrict_invites_enabled(restrict_setting) and policy),
        "domains": {
            domain: {
                "allows_sign_in": bool(providers),
                "allows_plus_tags": bool(providers & CREDENTIAL_PROVIDERS),
            }
            for domain, providers in policy.items()
        },
    }
