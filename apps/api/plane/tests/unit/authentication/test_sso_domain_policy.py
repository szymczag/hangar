# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.authentication.utils.sso_domain_policy import (
    FEDERATED_PROVIDERS,
    allowed_providers_for_email,
    invitation_rejection_reason,
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


class TestInvitationRejectionReason:
    """Which addresses may be invited, given the pinned domains."""

    PINNED = "corp.com=oidc"

    def test_pinned_domain_is_invitable(self):
        assert invitation_rejection_reason("person@corp.com", raw_setting=self.PINNED, restrict_setting="1") is None

    def test_outside_domain_is_refused_when_invites_are_confined(self):
        reason = invitation_rejection_reason("person@gmail.com", raw_setting=self.PINNED, restrict_setting="1")
        assert reason and "outside the domains" in reason

    def test_outside_domain_is_allowed_when_invites_are_not_confined(self):
        # The default. An instance that invites contractors keeps working.
        assert invitation_rejection_reason("person@gmail.com", raw_setting=self.PINNED, restrict_setting="0") is None

    def test_plus_tag_is_refused_on_a_directory_backed_domain(self):
        # The IdP issues no account carrying the tag, so the assertion at
        # sign-in would never match this invitation.
        reason = invitation_rejection_reason("person+team@corp.com", raw_setting=self.PINNED, restrict_setting="0")
        assert reason and "plus tag" in reason

    def test_plus_tag_is_refused_even_when_invites_are_not_confined(self):
        reason = invitation_rejection_reason("person+team@corp.com", raw_setting="corp.com", restrict_setting="0")
        assert reason and "plus tag" in reason

    def test_plus_tag_is_allowed_where_a_credential_provider_is_pinned(self):
        # magic-code proves the tagged mailbox, so the address is reachable.
        assert (
            invitation_rejection_reason(
                "person+team@corp.com", raw_setting="corp.com=oidc;magic-code", restrict_setting="1"
            )
            is None
        )

    def test_plus_tag_is_allowed_on_an_unpinned_domain(self):
        assert (
            invitation_rejection_reason("person+team@other.com", raw_setting=self.PINNED, restrict_setting="0") is None
        )

    def test_domain_denying_every_provider_is_refused_regardless_of_the_setting(self):
        # Pinned to an unknown provider name, which parses to an empty set.
        # Nobody can sign in, so no invitation there can be accepted.
        for restrict in ("0", "1"):
            reason = invitation_rejection_reason(
                "person@corp.com", raw_setting="corp.com=nope", restrict_setting=restrict
            )
            assert reason and "no sign-in method" in reason

    def test_no_policy_at_all_leaves_every_address_invitable(self):
        assert invitation_rejection_reason("person+tag@anywhere.com", raw_setting="", restrict_setting="1") is None

    def test_matching_is_case_insensitive(self):
        assert invitation_rejection_reason("PERSON@CORP.COM", raw_setting=self.PINNED, restrict_setting="1") is None
        reason = invitation_rejection_reason("PERSON+X@CORP.COM", raw_setting=self.PINNED, restrict_setting="1")
        assert reason and "plus tag" in reason

    def test_a_plus_in_the_domain_is_not_a_plus_in_the_local_part(self):
        # rpartition on "@" keeps the tag check to the mailbox name.
        assert invitation_rejection_reason("person@corp.com", raw_setting="corp.com", restrict_setting="1") is None
