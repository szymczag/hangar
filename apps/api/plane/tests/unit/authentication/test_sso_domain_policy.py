# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.authentication.utils.sso_domain_policy import (
    FEDERATED_PROVIDERS,
    allowed_providers_for_email,
    parse_enforced_domains,
)


def test_bare_domain_admits_federated_providers_and_refuses_credentials():
    policy = parse_enforced_domains("corp.com")
    assert policy["corp.com"] == set(FEDERATED_PROVIDERS)
    assert "email" not in policy["corp.com"]
    assert "magic-code" not in policy["corp.com"]


def test_explicit_provider_pins_domain_to_that_provider_alone():
    policy = parse_enforced_domains("corp.com=google")
    assert policy == {"corp.com": {"google"}}


def test_multiple_providers_and_entries_are_parsed_independently():
    policy = parse_enforced_domains(" corp.com=oidc;saml , eu.corp.com=google ")
    assert policy == {"corp.com": {"oidc", "saml"}, "eu.corp.com": {"google"}}


def test_unknown_provider_names_are_dropped_and_deny_the_domain():
    # An entry that names only unknown providers must fail closed rather than
    # silently admitting everything.
    policy = parse_enforced_domains("corp.com=nope")
    assert policy == {"corp.com": set()}
    assert allowed_providers_for_email("a@corp.com", raw_setting="corp.com=nope") == set()


def test_malformed_entry_does_not_disable_enforcement_for_the_others():
    policy = parse_enforced_domains("=google,,not/a/domain,corp.com=google")
    assert policy == {"corp.com": {"google"}}


def test_domains_are_matched_case_insensitively_and_idna_folded():
    assert allowed_providers_for_email("USER@CORP.COM", raw_setting="corp.com=google") == {"google"}
    assert allowed_providers_for_email("user@xn--bcher-kva.example", raw_setting="bücher.example=saml") == {"saml"}


def test_unlisted_domain_is_unrestricted():
    assert allowed_providers_for_email("user@other.com", raw_setting="corp.com=google") is None


def test_empty_setting_leaves_every_domain_unrestricted():
    assert allowed_providers_for_email("user@corp.com", raw_setting="") is None


def test_subdomains_are_not_covered_by_a_parent_entry():
    # Matching is exact: sub.corp.com is a different domain and an operator
    # who wants it pinned must list it.
    assert allowed_providers_for_email("user@sub.corp.com", raw_setting="corp.com=google") is None


@pytest.mark.parametrize("email", ["", None, "not-an-email"])
def test_addresses_without_a_domain_are_not_covered(email):
    assert allowed_providers_for_email(email, raw_setting="corp.com=google") is None


def test_address_with_empty_local_part_still_resolves_to_its_domain():
    # sanitize_email rejects this shape before the policy runs; resolving it to
    # the pinned domain anyway keeps the failure on the restrictive side.
    assert allowed_providers_for_email("@corp.com", raw_setting="corp.com=google") == {"google"}
