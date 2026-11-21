/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useId } from "react";
import { isEmpty } from "lodash-es";
import { Controller } from "react-hook-form";
// plane internal packages
import { Select, SelectContent, SelectItem, SelectList, SelectTrigger } from "@makeplane/propel/components/select";
import { Switch } from "@makeplane/propel/components/switch";
import { API_BASE_URL } from "@plane/constants";
import type { IFormattedInstanceConfiguration, TInstanceGoogleAuthenticationConfigurationKeys } from "@plane/types";
// components
import { OAuthProviderForm } from "@/components/authentication/oauth-provider-form";
import { CodeBlock } from "@/components/common/code-block";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import type { TControllerSwitchFormField } from "@/components/common/controller-switch";
import type { TCopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";
import { useOAuthProviderConfigForm } from "@/hooks/use-oauth-provider-config-form";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type GoogleConfigFormValues = Record<TInstanceGoogleAuthenticationConfigurationKeys, string>;

const GOOGLE_AUTH_MODE_OPTIONS: Record<string, string> = {
  generic: "Any Google account",
  workspace: "Only accounts in the Workspace domains listed below",
};

const GOOGLE_FORM_SWITCH_FIELD: TControllerSwitchFormField<GoogleConfigFormValues> = {
  name: "ENABLE_GOOGLE_SYNC",
  label: "Google",
};

export function InstanceGoogleConfigForm(props: Props) {
  const { config } = props;
  // ids
  const authModeLabelId = useId();
  const autoRedirectLabelId = useId();
  // store hooks
  const { configuredSecrets } = useInstance();
  // The API never returns a stored secret, so an empty field means either
  // "never set" or "set and unreadable". Only the first should block saving:
  // an empty value is understood server-side as "keep the existing secret",
  // so demanding it again just to change an unrelated setting asks the
  // operator to fetch a credential the instance already has.
  const isSecretConfigured = configuredSecrets.has("GOOGLE_CLIENT_SECRET");
  // form data
  const {
    control,
    formState: { errors },
    onSave,
  } = useOAuthProviderConfigForm<GoogleConfigFormValues>(
    "Google",
    {
      GOOGLE_CLIENT_ID: config["GOOGLE_CLIENT_ID"],
      GOOGLE_CLIENT_SECRET: "",
      ENABLE_GOOGLE_SYNC: config["ENABLE_GOOGLE_SYNC"] || "0",
      GOOGLE_AUTO_REDIRECT: config["GOOGLE_AUTO_REDIRECT"] || "0",
      GOOGLE_AUTH_MODE: config["GOOGLE_AUTH_MODE"] || "generic",
      GOOGLE_WORKSPACE_DOMAINS: config["GOOGLE_WORKSPACE_DOMAINS"] || "",
    },
    ["GOOGLE_CLIENT_SECRET"]
  );

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const GOOGLE_FORM_FIELDS: TControllerInputFormField<GoogleConfigFormValues>[] = [
    {
      key: "GOOGLE_WORKSPACE_DOMAINS",
      type: "text",
      label: "Allowed Workspace domains",
      description: (
        <>
          Comma-separated hosted domains. Required in workspace mode and checked against the signed{" "}
          <CodeBlock darkerShade>hd</CodeBlock> claim, so a matching email suffix alone is not enough. Anyone in a
          listed domain can sign in.
        </>
      ),
      placeholder: "example.com,subsidiary.example.com",
      error: Boolean(errors.GOOGLE_WORKSPACE_DOMAINS),
      required: false,
    },
    {
      key: "GOOGLE_CLIENT_ID",
      type: "text",
      label: "Client ID",
      description: (
        <>
          Your client ID lives in your Google API Console.{" "}
          <a
            href="https://developers.google.com/identity/protocols/oauth2/javascript-implicit-flow#creatingcred"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="Google OAuth client ID documentation"
          >
            Learn more
          </a>
        </>
      ),
      placeholder: "840195096245-0p2tstej9j5nc4l8o1ah2dqondscqc1g.apps.googleusercontent.com",
      error: Boolean(errors.GOOGLE_CLIENT_ID),
      required: true,
    },
    {
      key: "GOOGLE_CLIENT_SECRET",
      type: "password",
      label: "Client secret",
      description: (
        <>
          Your client secret should also be in your Google API Console.{" "}
          <a
            href="https://developers.google.com/identity/oauth2/web/guides/get-google-api-clientid"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="Google OAuth client secret documentation"
          >
            Learn more
          </a>
        </>
      ),
      placeholder: isSecretConfigured ? "Leave blank to keep the current secret" : "GOCShX-ADp4cI0kPqav1gGCBg5bE02E",
      error: Boolean(errors.GOOGLE_CLIENT_SECRET),
      required: !isSecretConfigured,
    },
  ];

  const GOOGLE_COMMON_SERVICE_DETAILS: TCopyField[] = [
    {
      key: "Origin_URL",
      label: "Origin URL",
      url: originURL,
      description: (
        <p>
          We will auto-generate this. Paste this into your{" "}
          <CodeBlock darkerShade>Authorized JavaScript origins</CodeBlock> field. For this OAuth client{" "}
          <a
            href="https://console.cloud.google.com/apis/credentials/oauthclient"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="Google Cloud Console OAuth client credentials"
          >
            here.
          </a>
        </p>
      ),
    },
  ];

  const GOOGLE_SERVICE_DETAILS: TCopyField[] = [
    {
      key: "Callback_URI",
      label: "Callback URI",
      url: `${originURL}/auth/google/callback/`,
      description: (
        <p>
          We will auto-generate this. Paste this into your <CodeBlock darkerShade>Authorized Redirect URI</CodeBlock>{" "}
          field. For this OAuth client{" "}
          <a
            href="https://console.cloud.google.com/apis/credentials/oauthclient"
            target="_blank"
            className="text-accent-primary hover:underline"
            rel="noreferrer"
            aria-label="Google Cloud Console OAuth client credentials"
          >
            here.
          </a>
        </p>
      ),
    },
    {
      key: "Space_Callback_URI",
      label: "Callback URI (spaces)",
      url: `${originURL}/auth/spaces/google/callback/`,
      description: (
        <p>
          Add this as a second <CodeBlock darkerShade>Authorized Redirect URI</CodeBlock> when public Spaces use Google
          authentication.
        </p>
      ),
    },
  ];

  const GOOGLE_AUTH_MODE_CONTROL = (
    <Controller
      control={control}
      name="GOOGLE_AUTH_MODE"
      render={({ field: { value, onChange } }) => (
        <div className="flex flex-col gap-1">
          <span id={authModeLabelId} className="text-body-xs-medium text-primary">
            Who may sign in with Google
          </span>
          {/* Two accepted values, spelled exactly. Typing them by hand
              meant a typo fell back to admitting every Google account,
              which is the opposite of what the operator intended. */}
          <Select
            items={GOOGLE_AUTH_MODE_OPTIONS}
            value={value || "generic"}
            onValueChange={(next) => onChange(next as string)}
          >
            <SelectTrigger variant="secondary" size="lg" aria-labelledby={authModeLabelId} />
            <SelectContent>
              <SelectList>
                {Object.entries(GOOGLE_AUTH_MODE_OPTIONS).map(([key, label]) => (
                  <SelectItem key={key} value={key} label={label} size="lg" />
                ))}
              </SelectList>
            </SelectContent>
          </Select>
          <div className="text-caption-sm-regular text-tertiary">
            {value === "workspace" ? (
              <>
                Checked against the signed <CodeBlock darkerShade>hd</CodeBlock> claim, so a matching email suffix is
                not enough. It admits <em>every</em> account in a listed domain — Google issues no organizational-unit
                or group claim, so it cannot be narrowed further here. Narrow it with invites, or with Domain policy.
              </>
            ) : (
              <>
                Anyone with a Google account can sign in, including personal gmail.com addresses. Choose the other
                option to limit sign-in to your own Workspace domains.
              </>
            )}
          </div>
        </div>
      )}
    />
  );

  const GOOGLE_AUTO_REDIRECT_CONTROL = (
    <Controller
      control={control}
      name="GOOGLE_AUTO_REDIRECT"
      render={({ field: { value, onChange } }) => {
        const isEnabled = value === "1";
        return (
          <div className="flex items-start justify-between gap-4 py-1">
            <div className="flex min-w-0 flex-col gap-1">
              <span id={autoRedirectLabelId} className="text-body-sm-medium text-primary">
                Automatically start Google sign-in
              </span>
              <p className="text-caption-sm-regular text-tertiary">
                Skip the sign-in chooser when Google is the only enabled login method. OAuth errors and an explicit
                sign-out still show the Google button so people can recover or switch accounts.
              </p>
            </div>
            <Switch
              checked={isEnabled}
              onCheckedChange={() => onChange(isEnabled ? "0" : "1")}
              size="sm"
              aria-labelledby={autoRedirectLabelId}
            />
          </div>
        );
      }}
    />
  );

  return (
    <OAuthProviderForm
      providerName="Google"
      control={control}
      formFields={GOOGLE_FORM_FIELDS}
      switchField={GOOGLE_FORM_SWITCH_FIELD}
      onSave={onSave}
      serviceDetails={GOOGLE_COMMON_SERVICE_DETAILS}
      webServiceDetails={GOOGLE_SERVICE_DETAILS}
      leadingControls={GOOGLE_AUTH_MODE_CONTROL}
      trailingControls={GOOGLE_AUTO_REDIRECT_CONTROL}
    />
  );
}
