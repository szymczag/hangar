/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The invitation rules, applied before the round trip.
 *
 * The server refuses these addresses either way — this only moves the refusal
 * to the field the admin is typing in, rather than an error toast after
 * submitting a batch. The three rules mirror `invitation_rejection_reason` in
 * `plane/authentication/utils/sso_domain_policy.py`; keep them in step.
 */

export type TInvitePolicyDomain = {
  /** False when the domain is pinned to no provider: nobody there can sign in. */
  allows_sign_in: boolean;
  /** True only where a credential provider can still prove a tagged mailbox. */
  allows_plus_tags: boolean;
};

export type TInvitePolicy = {
  restrict_to_domains: boolean;
  domains: Record<string, TInvitePolicyDomain>;
};

export type TInviteRejection =
  | { rule: "outside_domain"; domains: string[] }
  | { rule: "plus_tag"; domain: string }
  | { rule: "blocked_domain"; domain: string };

/**
 * Why `email` cannot be invited, or null if it can.
 *
 * An address still being typed is not reported: an empty or half-written one
 * would flag every keystroke, and the required/pattern rules already cover it.
 */
export function inviteRejection(email: string, policy: TInvitePolicy | undefined): TInviteRejection | null {
  if (!policy) return null;

  const address = (email ?? "").trim();
  const separator = address.lastIndexOf("@");
  if (separator <= 0) return null;

  const localPart = address.slice(0, separator);
  // Matching is exact and case-insensitive, as it is on the server. A trailing
  // dot is the one thing folded, since corp.com. is the same domain.
  const domain = address
    .slice(separator + 1)
    .toLowerCase()
    .replace(/\.$/, "");
  // "person@" while typing has no domain to judge.
  if (!domain) return null;

  const pinned = policy.domains[domain];

  if (!pinned) {
    return policy.restrict_to_domains ? { rule: "outside_domain", domains: Object.keys(policy.domains) } : null;
  }

  if (!pinned.allows_sign_in) return { rule: "blocked_domain", domain };

  if (localPart.includes("+") && !pinned.allows_plus_tags) return { rule: "plus_tag", domain };

  return null;
}
