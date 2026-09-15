/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import type { TInvitePolicy } from "./invite-policy";
import { inviteRejection } from "./invite-policy";

const CONFINED: TInvitePolicy = {
  restrict_to_domains: true,
  domains: { "corp.com": { allows_sign_in: true, allows_plus_tags: false } },
};

const UNCONFINED: TInvitePolicy = { ...CONFINED, restrict_to_domains: false };

describe("inviteRejection", () => {
  it("accepts an address on a pinned domain", () => {
    expect(inviteRejection("person@corp.com", CONFINED)).toBeNull();
  });

  it("refuses an address outside the pinned domains when confined", () => {
    expect(inviteRejection("person@gmail.com", CONFINED)).toEqual({
      rule: "outside_domain",
      domains: ["corp.com"],
    });
  });

  it("accepts an address outside the pinned domains when not confined", () => {
    expect(inviteRejection("person@gmail.com", UNCONFINED)).toBeNull();
  });

  it("refuses a plus tag on a pinned domain whether or not invites are confined", () => {
    expect(inviteRejection("person+team@corp.com", CONFINED)).toEqual({ rule: "plus_tag", domain: "corp.com" });
    expect(inviteRejection("person+team@corp.com", UNCONFINED)).toEqual({ rule: "plus_tag", domain: "corp.com" });
  });

  it("keeps plus tags where a credential provider can still prove the mailbox", () => {
    const policy: TInvitePolicy = {
      restrict_to_domains: true,
      domains: { "corp.com": { allows_sign_in: true, allows_plus_tags: true } },
    };
    expect(inviteRejection("person+team@corp.com", policy)).toBeNull();
  });

  it("refuses a domain that allows no sign-in method at all", () => {
    const policy: TInvitePolicy = {
      restrict_to_domains: false,
      domains: { "corp.com": { allows_sign_in: false, allows_plus_tags: false } },
    };
    expect(inviteRejection("person@corp.com", policy)).toEqual({ rule: "blocked_domain", domain: "corp.com" });
  });

  it("matches the domain case-insensitively and ignores a trailing dot", () => {
    expect(inviteRejection("PERSON+X@CORP.COM", CONFINED)).toEqual({ rule: "plus_tag", domain: "corp.com" });
    expect(inviteRejection("person@corp.com.", CONFINED)).toBeNull();
  });

  it("says nothing about an address still being typed", () => {
    // required/pattern already cover these; flagging them would fire on every keystroke.
    for (const value of ["", "  ", "person", "person@", "@corp.com"]) {
      expect(inviteRejection(value, CONFINED)).toBeNull();
    }
  });

  it("says nothing when the policy could not be read", () => {
    expect(inviteRejection("person+team@gmail.com", undefined)).toBeNull();
  });

  it("does not treat a plus in the domain as a tag", () => {
    expect(inviteRejection("person@corp.com", CONFINED)).toBeNull();
  });
});
