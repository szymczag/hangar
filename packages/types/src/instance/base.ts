/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IUserLite } from "../users";
import type {
  TInstanceAIConfigurationKeys,
  TInstanceEmailConfigurationKeys,
  TInstanceImageConfigurationKeys,
  TInstanceAuthenticationKeys,
  TInstanceWorkspaceConfigurationKeys,
  TCoreLoginMediums,
} from "./";
import type { TExtendedLoginMediums } from "./auth-ee";

export interface IInstanceInfo {
  instance: IInstance;
  config: IInstanceConfig;
}

export interface IInstanceTelemetryConfiguration {
  collector_configured: boolean;
  metrics_protocol: "grpc" | "http" | null;
}

export interface IInstanceEmailDeliveryConfiguration {
  provider: "smtp" | "ses_smtp" | "ses_api";
  is_deployment_managed: boolean;
  durable_delivery_enabled: boolean;
  openpgp_enabled: boolean;
  sender: string;
  reply_to: string;
  ses: {
    region: string;
    account_id: string;
    access_key_id: string;
    auth_configuration_set: string;
    notification_configuration_set: string;
    events_queue_url: string;
    events_topic_arn: string;
  } | null;
}

export interface IProductMetadata {
  name: "Hangar";
  version: string;
  repository_url: string;
  source_url: string;
  documentation_url: string;
  issues_url: string;
  security_url: string;
  terms_url: string | null;
  privacy_url: string | null;
}

export interface IInstance {
  id: string;
  created_at: string;
  updated_at: string;
  instance_name: string | undefined;
  whitelist_emails: string | undefined;
  instance_id: string | undefined;
  license_key: string | undefined;
  current_version: string | undefined;
  latest_version: string | undefined;
  last_checked_at: string | undefined;
  namespace: string | undefined;
  is_telemetry_enabled: boolean;
  is_support_required: boolean;
  is_activated: boolean;
  is_setup_done: boolean;
  is_signup_screen_visited: boolean;
  user_count: number | undefined;
  is_verified: boolean;
  created_by: string | undefined;
  updated_by: string | undefined;
  workspaces_exist: boolean;
}

export type TInstanceBrandingConfigurationKeys =
  | "INSTANCE_BRANDING_NAME"
  | "INSTANCE_SIGN_IN_HEADER"
  | "INSTANCE_SIGN_IN_SUBHEADER"
  | "INSTANCE_ACCENT_COLOR"
  | "INSTANCE_LOGIN_BACKDROP_COLOR";

export interface IInstanceConfig {
  product: IProductMetadata;
  enable_signup: boolean;
  is_workspace_creation_disabled: boolean;
  is_google_enabled: boolean;
  is_google_auto_redirect_enabled: boolean;
  is_github_enabled: boolean;
  is_gitlab_enabled: boolean;
  is_gitea_enabled: boolean;
  is_magic_login_enabled: boolean;
  is_email_password_enabled: boolean;
  // Fork (see FORK.md)
  is_oidc_enabled: boolean;
  oidc_provider_name: string | undefined;
  is_saml_enabled: boolean;
  saml_provider_name: string | undefined;
  is_todoist_imports_enabled?: boolean;
  // Sign-in page branding. Empty means the built-in wording and wordmark.
  branding_name?: string;
  sign_in_header?: string;
  sign_in_subheader?: string;
  logo_url?: string;
  login_background_url?: string;
  /** Empty unless it is a plain hex colour; validated on write and on read. */
  accent_color?: string;
  login_backdrop_color?: string;
  show_license_notice?: boolean;
  /** Providers that overwrite name and avatar on every sign-in. */
  provider_managed_profiles?: string[];
  // Fork: workspace role needed before an account may mint an API token, so the
  // app can offer the feature only where creating one would succeed.
  api_token_minimum_role?: number;
  // Fork: the instance forces every project, page and view private and refuses
  // to publish anything publicly, so the clients must not offer the choice.
  force_private_visibility?: boolean;
  // Fork: whether the application may link to hosts this instance does not run.
  // The AGPL source offer is exempt and always shown.
  show_external_links?: boolean;
  github_app_name: string | undefined;
  slack_client_id: string | undefined;
  posthog_api_key: string | undefined;
  posthog_host: string | undefined;
  has_unsplash_configured: boolean;
  has_llm_configured: boolean;
  file_size_limit: number | undefined;
  is_smtp_configured: boolean;
  app_base_url: string | undefined;
  space_base_url: string | undefined;
  admin_base_url: string | undefined;
  is_self_managed: boolean;
  instance_changelog_url?: string;
}

export interface IInstanceAdmin {
  created_at: string;
  created_by: string;
  id: string;
  instance: string;
  role: string;
  updated_at: string;
  updated_by: string;
  user: string;
  user_detail: IUserLite;
}

// Fork (see FORK.md): reported by the API, never written. Tells the panel
// whether stored configuration is read back at all, or whether the deployment
// environment decides and every form would be a no-op.
export type TInstanceConfigurationSourceKey = "CONFIGURATION_SOURCE";

export type TInstanceConfigurationKeys =
  | TInstanceAIConfigurationKeys
  | TInstanceEmailConfigurationKeys
  | TInstanceImageConfigurationKeys
  | TInstanceAuthenticationKeys
  | TInstanceWorkspaceConfigurationKeys
  | TInstanceBrandingConfigurationKeys
  | "INSTANCE_LOGO_ASSET_ID"
  | "INSTANCE_LOGIN_BACKGROUND_ASSET_ID"
  | "INSTANCE_SHOW_LICENSE_NOTICE"
  | "INSTANCE_SHOW_EXTERNAL_LINKS"
  | TInstanceConfigurationSourceKey;

export interface IInstanceConfiguration {
  id: string;
  created_at: string;
  updated_at: string;
  key: TInstanceConfigurationKeys;
  value: string;
  created_by: string | null;
  updated_by: string | null;
  // Sent only for encrypted keys, whose `value` is always returned empty
  // because secrets are write-only. It is the only way a form can tell a secret
  // that has never been set from one it simply cannot read back.
  is_configured?: boolean;
}

// Fork (see FORK.md): read-only report of who has an account and how they
// sign in. `status` says what pinning a domain to `provider` would do to the
// account: already bound, adopted on next sign-in, or refused until imported.
export type TInstanceUserSignInStatus = "federated" | "adoptable" | "needs-import" | "password-only";

export type TInstanceUserFederatedIdentity = {
  provider: string;
  issuer: string;
  last_authenticated_at: string | null;
};

export type TInstanceUser = {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  has_password: boolean;
  last_login_at: string | null;
  federated_identities: TInstanceUserFederatedIdentity[];
  oauth_accounts: string[];
  status: TInstanceUserSignInStatus;
};

export type TInstanceUserListResponse = {
  results: TInstanceUser[];
  next_cursor?: string;
  prev_cursor?: string;
  next_page_results?: boolean;
  prev_page_results?: boolean;
  count?: number;
  total_count?: number;
};

export type IFormattedInstanceConfiguration = {
  [key in TInstanceConfigurationKeys]: string;
};

export type TLoginMediums = TCoreLoginMediums | TExtendedLoginMediums;
