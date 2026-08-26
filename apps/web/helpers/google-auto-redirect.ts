/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IInstanceConfig } from "@plane/types";

type TGoogleAutoRedirectConfig = Pick<
  IInstanceConfig,
  | "is_google_auto_redirect_enabled"
  | "is_google_enabled"
  | "is_github_enabled"
  | "is_gitlab_enabled"
  | "is_gitea_enabled"
  | "is_magic_login_enabled"
  | "is_email_password_enabled"
  | "is_oidc_enabled"
  | "is_saml_enabled"
>;

type TGoogleAutoRedirectContext = {
  hasAuthenticationError: boolean;
  wasSignedOut: boolean;
};

export function shouldAutoRedirectToGoogle(
  config: TGoogleAutoRedirectConfig | undefined,
  context: TGoogleAutoRedirectContext
): boolean {
  if (!config || context.hasAuthenticationError || context.wasSignedOut) return false;

  return (
    config.is_google_auto_redirect_enabled &&
    config.is_google_enabled &&
    !config.is_github_enabled &&
    !config.is_gitlab_enabled &&
    !config.is_gitea_enabled &&
    !config.is_magic_login_enabled &&
    !config.is_email_password_enabled &&
    !config.is_oidc_enabled &&
    !config.is_saml_enabled
  );
}
