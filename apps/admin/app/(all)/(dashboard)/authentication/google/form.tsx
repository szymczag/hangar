/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { Controller, useForm } from "react-hook-form";
import { Monitor } from "lucide-react";
// plane internal packages
import { API_BASE_URL } from "@plane/constants";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceGoogleAuthenticationConfigurationKeys } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
// components
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import type { TControllerSwitchFormField } from "@/components/common/controller-switch";
import { ControllerSwitch } from "@/components/common/controller-switch";
import { ControllerInput } from "@/components/common/controller-input";
import type { TCopyField } from "@/components/common/copy-field";
import { CopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type GoogleConfigFormValues = Record<TInstanceGoogleAuthenticationConfigurationKeys, string>;

const GOOGLE_FORM_SWITCH_FIELD: TControllerSwitchFormField<GoogleConfigFormValues> = {
  name: "ENABLE_GOOGLE_SYNC",
  label: "Google",
};

export function InstanceGoogleConfigForm(props: Props) {
  const { config } = props;
  // states
  const [isDiscardChangesModalOpen, setIsDiscardChangesModalOpen] = useState(false);
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  // form data
  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<GoogleConfigFormValues>({
    defaultValues: {
      GOOGLE_CLIENT_ID: config["GOOGLE_CLIENT_ID"],
      GOOGLE_CLIENT_SECRET: config["GOOGLE_CLIENT_SECRET"],
      ENABLE_GOOGLE_SYNC: config["ENABLE_GOOGLE_SYNC"] || "0",
      GOOGLE_AUTO_REDIRECT: config["GOOGLE_AUTO_REDIRECT"] || "0",
      GOOGLE_AUTH_MODE: config["GOOGLE_AUTH_MODE"] || "generic",
      GOOGLE_WORKSPACE_DOMAINS: config["GOOGLE_WORKSPACE_DOMAINS"] || "",
    },
  });

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
      placeholder: "GOCShX-ADp4cI0kPqav1gGCBg5bE02E",
      error: Boolean(errors.GOOGLE_CLIENT_SECRET),
      required: true,
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

  const onSubmit = async (formData: GoogleConfigFormValues) => {
    const payload: Partial<GoogleConfigFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Your Google authentication is configured. You should test it now.",
      });
      reset({
        GOOGLE_CLIENT_ID: response.find((item) => item.key === "GOOGLE_CLIENT_ID")?.value,
        GOOGLE_CLIENT_SECRET: response.find((item) => item.key === "GOOGLE_CLIENT_SECRET")?.value,
        ENABLE_GOOGLE_SYNC: response.find((item) => item.key === "ENABLE_GOOGLE_SYNC")?.value,
        GOOGLE_AUTO_REDIRECT: response.find((item) => item.key === "GOOGLE_AUTO_REDIRECT")?.value,
        GOOGLE_AUTH_MODE: response.find((item) => item.key === "GOOGLE_AUTH_MODE")?.value,
        GOOGLE_WORKSPACE_DOMAINS: response.find((item) => item.key === "GOOGLE_WORKSPACE_DOMAINS")?.value,
      });
    } catch (err) {
      console.error(err);
    }
  };

  const handleGoBack = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
    if (isDirty) {
      e.preventDefault();
      setIsDiscardChangesModalOpen(true);
    }
  };

  return (
    <>
      <ConfirmDiscardModal
        isOpen={isDiscardChangesModalOpen}
        onDiscardHref="/authentication"
        handleClose={() => setIsDiscardChangesModalOpen(false)}
      />
      <div className="flex flex-col gap-8">
        <div className="grid w-full grid-cols-2 gap-x-12 gap-y-8">
          <div className="col-span-2 flex flex-col gap-y-4 pt-1 md:col-span-1">
            <div className="pt-2.5 text-18 font-medium">Google-provided details for Hangar</div>
            <Controller
              control={control}
              name="GOOGLE_AUTH_MODE"
              render={({ field: { value, onChange } }) => (
                <div className="flex flex-col gap-1">
                  <h4 className="text-13 text-secondary">Who may sign in with Google</h4>
                  {/* Two accepted values, spelled exactly. Typing them by hand
                      meant a typo fell back to admitting every Google account,
                      which is the opposite of what the operator intended. */}
                  <select
                    className="rounded-md border border-strong bg-surface-1 px-3 py-2 text-14"
                    value={value || "generic"}
                    onChange={(event) => onChange(event.target.value)}
                  >
                    <option value="generic">Any Google account</option>
                    <option value="workspace">Only accounts in the Workspace domains listed below</option>
                  </select>
                  <div className="text-11 text-tertiary">
                    {value === "workspace" ? (
                      <>
                        Checked against the signed <CodeBlock darkerShade>hd</CodeBlock> claim, so a matching email
                        suffix is not enough. It admits <em>every</em> account in a listed domain — Google issues no
                        organizational-unit or group claim, so it cannot be narrowed further here. Narrow it with
                        invites, or with Domain policy.
                      </>
                    ) : (
                      <>
                        Anyone with a Google account can sign in, including personal gmail.com addresses. Choose the
                        other option to limit sign-in to your own Workspace domains.
                      </>
                    )}
                  </div>
                </div>
              )}
            />
            {GOOGLE_FORM_FIELDS.map((field) => (
              <ControllerInput
                key={field.key}
                control={control}
                type={field.type}
                name={field.key}
                label={field.label}
                description={field.description}
                placeholder={field.placeholder}
                error={field.error}
                required={field.required}
              />
            ))}
            <ControllerSwitch control={control} field={GOOGLE_FORM_SWITCH_FIELD} />
            <Controller
              control={control}
              name="GOOGLE_AUTO_REDIRECT"
              render={({ field: { value, onChange } }) => {
                const isEnabled = value === "1";
                return (
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex flex-col gap-1">
                      <h4 className="text-sm text-custom-text-300">Automatically start Google sign-in</h4>
                      <p className="text-11 text-tertiary">
                        Skip the sign-in chooser when Google is the only enabled login method. OAuth errors and an
                        explicit sign-out still show the Google button so people can recover or switch accounts.
                      </p>
                    </div>
                    <ToggleSwitch value={isEnabled} onChange={() => onChange(isEnabled ? "0" : "1")} size="sm" />
                  </div>
                );
              }}
            />
            <div className="flex flex-col gap-1 pt-4">
              <div className="flex items-center gap-4">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={(e) => void handleSubmit(onSubmit)(e)}
                  loading={isSubmitting}
                  disabled={!isDirty}
                >
                  {isSubmitting ? "Saving" : "Save changes"}
                </Button>
                <Link href="/authentication" className={getButtonStyling("secondary", "lg")} onClick={handleGoBack}>
                  Go back
                </Link>
              </div>
            </div>
          </div>
          <div className="col-span-2 flex flex-col gap-y-6 md:col-span-1">
            <div className="pt-2 text-18 font-medium">Hangar-provided details for Google</div>

            <div className="flex flex-col gap-y-4">
              {/* common service details */}
              <div className="flex flex-col gap-y-4 rounded-lg bg-layer-1 px-6 py-4">
                {GOOGLE_COMMON_SERVICE_DETAILS.map((field) => (
                  <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
                ))}
              </div>

              {/* web service details */}
              <div className="flex flex-col overflow-hidden rounded-lg">
                <div className="flex items-center gap-x-3 bg-layer-3 px-6 py-3 text-11 font-medium text-secondary uppercase">
                  <Monitor className="h-3 w-3" />
                  Web
                </div>
                <div className="flex flex-col gap-y-4 bg-layer-1 px-6 py-4">
                  {GOOGLE_SERVICE_DETAILS.map((field) => (
                    <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
