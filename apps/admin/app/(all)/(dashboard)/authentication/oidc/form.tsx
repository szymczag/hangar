/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isEmpty } from "lodash-es";
// plane internal packages
import { API_BASE_URL } from "@plane/constants";
import type { IFormattedInstanceConfiguration, TInstanceOIDCAuthenticationConfigurationKeys } from "@plane/types";
// components
import { OAuthProviderForm } from "@/components/authentication/oauth-provider-form";
import { CodeBlock } from "@/components/common/code-block";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import type { TCopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";
import { useOAuthProviderConfigForm } from "@/hooks/use-oauth-provider-config-form";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type OIDCConfigFormValues = Record<TInstanceOIDCAuthenticationConfigurationKeys, string>;

export function InstanceOIDCConfigForm(props: Props) {
  const { config } = props;
  // store hooks
  const { configuredSecrets } = useInstance();
  // The API never returns a stored secret, so an empty field means either
  // "never set" or "set and unreadable". Only the first should block saving:
  // an empty value is understood server-side as "keep the existing secret",
  // so demanding it again just to change an unrelated setting asks the
  // operator to fetch a credential the instance already has.
  const isSecretConfigured = configuredSecrets.has("OIDC_CLIENT_SECRET");
  // form data
  const {
    control,
    formState: { errors },
    onSave,
  } = useOAuthProviderConfigForm<OIDCConfigFormValues>(
    "OIDC",
    {
      OIDC_ISSUER: config["OIDC_ISSUER"],
      OIDC_CLIENT_ID: config["OIDC_CLIENT_ID"],
      OIDC_CLIENT_SECRET: "",
      OIDC_PROVIDER_NAME: config["OIDC_PROVIDER_NAME"] || "OIDC",
    },
    ["OIDC_CLIENT_SECRET"]
  );

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const OIDC_FORM_FIELDS: TControllerInputFormField<OIDCConfigFormValues>[] = [
    {
      key: "OIDC_ISSUER",
      type: "text",
      label: "Issuer URL",
      description: (
        <>
          The issuer URL of your identity provider, without the{" "}
          <CodeBlock darkerShade>/.well-known/openid-configuration</CodeBlock> suffix. Use an HTTPS endpoint that
          negotiates TLS 1.3; providers and reverse proxies limited to TLS 1.2 are not supported. The token, JWKS, and
          userinfo endpoints in the discovery document must use the same origin.
        </>
      ),
      placeholder: "https://accounts.example.com",
      error: Boolean(errors.OIDC_ISSUER),
      required: true,
    },
    {
      key: "OIDC_CLIENT_ID",
      type: "text",
      label: "Client ID",
      description: <>From the OAuth/OIDC client you registered with your identity provider.</>,
      placeholder: "70a44354520df8bd9bcd",
      error: Boolean(errors.OIDC_CLIENT_ID),
      required: true,
    },
    {
      key: "OIDC_CLIENT_SECRET",
      type: "password",
      label: "Client secret",
      description: <>The client secret issued by your identity provider for this client.</>,
      placeholder: isSecretConfigured
        ? "Leave blank to keep the current secret"
        : "9b0050f94ec1b744e32ce79ea4ffacd40d4119cb",
      error: Boolean(errors.OIDC_CLIENT_SECRET),
      required: !isSecretConfigured,
    },
    {
      key: "OIDC_PROVIDER_NAME",
      type: "text",
      label: "Provider name",
      description: <>Shown on the sign-in button, e.g. &quot;Continue with Okta&quot;.</>,
      placeholder: "Okta",
      error: Boolean(errors.OIDC_PROVIDER_NAME),
      required: false,
    },
  ];

  const OIDC_SERVICE_FIELD: TCopyField[] = [
    {
      key: "Callback_URI",
      label: "Callback URI",
      url: `${originURL}/auth/oidc/callback/`,
      description: (
        <>
          We will auto-generate this. Paste this into the <CodeBlock darkerShade>Redirect URI</CodeBlock> field of your
          identity provider&apos;s client configuration.
        </>
      ),
    },
    {
      key: "Space_Callback_URI",
      label: "Callback URI (spaces)",
      url: `${originURL}/auth/spaces/oidc/callback/`,
      description: (
        <>
          Add this as a second <CodeBlock darkerShade>Redirect URI</CodeBlock> if you use public Spaces.
        </>
      ),
    },
  ];

  return (
    <OAuthProviderForm
      providerName="IdP"
      control={control}
      formFields={OIDC_FORM_FIELDS}
      onSave={onSave}
      serviceDetails={OIDC_SERVICE_FIELD}
    />
  );
}
