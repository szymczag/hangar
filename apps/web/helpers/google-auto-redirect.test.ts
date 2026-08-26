/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { shouldAutoRedirectToGoogle } from "./google-auto-redirect";

const googleOnlyConfig = {
  is_google_auto_redirect_enabled: true,
  is_google_enabled: true,
  is_github_enabled: false,
  is_gitlab_enabled: false,
  is_gitea_enabled: false,
  is_magic_login_enabled: false,
  is_email_password_enabled: false,
  is_oidc_enabled: false,
  is_saml_enabled: false,
};

const normalVisit = { hasAuthenticationError: false, wasSignedOut: false };

describe("shouldAutoRedirectToGoogle", () => {
  it("redirects when the operator enabled it and Google is the only login method", () => {
    expect(shouldAutoRedirectToGoogle(googleOnlyConfig, normalVisit)).toBe(true);
  });

  it("does not redirect without loaded configuration or when the setting is disabled", () => {
    expect(shouldAutoRedirectToGoogle(undefined, normalVisit)).toBe(false);
    expect(
      shouldAutoRedirectToGoogle({ ...googleOnlyConfig, is_google_auto_redirect_enabled: false }, normalVisit)
    ).toBe(false);
  });

  it.each([
    "is_github_enabled",
    "is_gitlab_enabled",
    "is_gitea_enabled",
    "is_magic_login_enabled",
    "is_email_password_enabled",
    "is_oidc_enabled",
    "is_saml_enabled",
  ] as const)("does not redirect when %s is enabled", (method) => {
    expect(shouldAutoRedirectToGoogle({ ...googleOnlyConfig, [method]: true }, normalVisit)).toBe(false);
  });

  it("does not redirect after an OAuth error", () => {
    expect(shouldAutoRedirectToGoogle(googleOnlyConfig, { hasAuthenticationError: true, wasSignedOut: false })).toBe(
      false
    );
  });

  it("does not redirect immediately after an explicit sign-out", () => {
    expect(shouldAutoRedirectToGoogle(googleOnlyConfig, { hasAuthenticationError: false, wasSignedOut: true })).toBe(
      false
    );
  });
});
