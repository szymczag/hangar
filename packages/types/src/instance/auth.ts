/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TCoreInstanceAuthenticationModeKeys =
  | "unique-codes"
  | "passwords-login"
  | "google"
  | "github"
  | "gitlab"
  | "gitea";

// Fork (see FORK.md): extended modes come from the designated auth-ee hook
import type { TExtendedInstanceAuthenticationModeKeys } from "./auth-ee";

export type TInstanceAuthenticationModeKeys =
  | TCoreInstanceAuthenticationModeKeys
  | TExtendedInstanceAuthenticationModeKeys;

export type TInstanceAuthenticationModes = {
  key: TInstanceAuthenticationModeKeys;
  name: string;
  description: string;
  icon: React.ReactNode;
  config: React.ReactNode;
  enabledConfigKey: TInstanceAuthenticationMethodKeys;
  unavailable?: boolean;
};

export type TInstanceAuthenticationMethodKeys =
  | "ENABLE_SIGNUP"
  | "ENABLE_MAGIC_LINK_LOGIN"
  | "ENABLE_EMAIL_PASSWORD"
  | "IS_GOOGLE_ENABLED"
  | "IS_GITHUB_ENABLED"
  | "IS_GITLAB_ENABLED"
  | "IS_GITEA_ENABLED"
  // Fork (see FORK.md)
  | "IS_OIDC_ENABLED"
  | "IS_SAML_ENABLED";

export type TInstanceGoogleAuthenticationConfigurationKeys =
  | "GOOGLE_CLIENT_ID"
  | "GOOGLE_CLIENT_SECRET"
  | "ENABLE_GOOGLE_SYNC"
  | "GOOGLE_AUTH_MODE"
  | "GOOGLE_WORKSPACE_DOMAINS";

export type TInstanceGithubAuthenticationConfigurationKeys =
  | "GITHUB_CLIENT_ID"
  | "GITHUB_CLIENT_SECRET"
  | "GITHUB_ORGANIZATION_ID"
  | "ENABLE_GITHUB_SYNC";

export type TInstanceGitlabAuthenticationConfigurationKeys =
  | "GITLAB_HOST"
  | "GITLAB_CLIENT_ID"
  | "GITLAB_CLIENT_SECRET"
  | "ENABLE_GITLAB_SYNC";

export type TInstanceGiteaAuthenticationConfigurationKeys =
  | "GITEA_HOST"
  | "GITEA_CLIENT_ID"
  | "GITEA_CLIENT_SECRET"
  | "ENABLE_GITEA_SYNC";

// Fork (see FORK.md): OIDC configuration keys
export type TInstanceOIDCAuthenticationConfigurationKeys =
  | "OIDC_ISSUER"
  | "OIDC_CLIENT_ID"
  | "OIDC_CLIENT_SECRET"
  | "OIDC_PROVIDER_NAME";

// Fork (see FORK.md): SAML configuration keys
export type TInstanceSAMLAuthenticationConfigurationKeys =
  | "SAML_IDP_ENTITY_ID"
  | "SAML_IDP_SSO_URL"
  | "SAML_IDP_CERTIFICATE"
  | "SAML_PROVIDER_NAME"
  | "SAML_ATTR_EMAIL"
  | "SAML_ATTR_FIRST_NAME"
  | "SAML_ATTR_LAST_NAME"
  | "SAML_ATTR_SUBJECT";

// Fork (see FORK.md): domain policy keys. Not tied to one provider — they
// govern which provider may assert a domain and where its users land.
export type TInstanceSSODomainPolicyConfigurationKeys = "SSO_ENFORCED_DOMAINS" | "SSO_AUTO_JOIN_WORKSPACES";


export type TInstanceAuthenticationConfigurationKeys =
  | TInstanceGoogleAuthenticationConfigurationKeys
  | TInstanceGithubAuthenticationConfigurationKeys
  | TInstanceGitlabAuthenticationConfigurationKeys
  | TInstanceGiteaAuthenticationConfigurationKeys
  | TInstanceOIDCAuthenticationConfigurationKeys
  | TInstanceSAMLAuthenticationConfigurationKeys
  | TInstanceSSODomainPolicyConfigurationKeys;

export type TInstanceAuthenticationKeys = TInstanceAuthenticationMethodKeys | TInstanceAuthenticationConfigurationKeys;

export type TGetBaseAuthenticationModeProps = {
  disabled: boolean;
  updateConfig: (key: TInstanceAuthenticationMethodKeys, value: string) => void;
  resolvedTheme: string | undefined;
};

export type TOAuthOption = {
  id: string;
  text: string;
  icon: React.ReactNode;
  onClick: () => void;
  enabled?: boolean;
};

export type TOAuthConfigs = {
  isOAuthEnabled: boolean;
  oAuthOptions: TOAuthOption[];
};

export type TCoreLoginMediums = "email" | "magic-code" | "github" | "gitlab" | "google" | "gitea";
