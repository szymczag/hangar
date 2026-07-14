/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { useForm } from "react-hook-form";
// plane internal packages
import { API_BASE_URL } from "@plane/constants";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceSAMLAuthenticationConfigurationKeys } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
import type { TCopyField } from "@/components/common/copy-field";
import { CopyField } from "@/components/common/copy-field";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type SAMLConfigFormValues = Record<TInstanceSAMLAuthenticationConfigurationKeys, string>;

const isValidHttpsUrl = (value: string) => {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && Boolean(url.hostname) && !url.username && !url.password && !url.hash;
  } catch {
    return false;
  }
};

export function InstanceSAMLConfigForm(props: Props) {
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
    setError,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<SAMLConfigFormValues>({
    defaultValues: {
      SAML_IDP_ENTITY_ID: config["SAML_IDP_ENTITY_ID"],
      SAML_IDP_SSO_URL: config["SAML_IDP_SSO_URL"],
      SAML_IDP_CERTIFICATE: config["SAML_IDP_CERTIFICATE"],
      SAML_PROVIDER_NAME: config["SAML_PROVIDER_NAME"] || "SAML",
      SAML_ATTR_EMAIL: config["SAML_ATTR_EMAIL"],
      SAML_ATTR_FIRST_NAME: config["SAML_ATTR_FIRST_NAME"],
      SAML_ATTR_LAST_NAME: config["SAML_ATTR_LAST_NAME"],
      SAML_ATTR_SUBJECT: config["SAML_ATTR_SUBJECT"],
    },
  });

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";

  const SAML_FORM_FIELDS: TControllerInputFormField[] = [
    {
      key: "SAML_IDP_ENTITY_ID",
      type: "text",
      label: "IdP entity ID",
      description: <>The identity provider&apos;s entity ID (issuer), from its metadata.</>,
      placeholder: "https://idp.example.com/metadata",
      error: Boolean(errors.SAML_IDP_ENTITY_ID),
      required: true,
    },
    {
      key: "SAML_IDP_SSO_URL",
      type: "text",
      label: "IdP single sign-on URL",
      description: (
        <>
          The HTTPS HTTP-Redirect SSO endpoint of your identity provider. Configure the IdP or its reverse proxy to
          require TLS 1.3.
        </>
      ),
      placeholder: "https://idp.example.com/sso/saml",
      error: Boolean(errors.SAML_IDP_SSO_URL),
      required: true,
    },
    {
      key: "SAML_IDP_CERTIFICATE",
      type: "text",
      label: "IdP signing certificate",
      description: (
        <>Paste the identity provider&apos;s X.509 signing certificate (PEM). Formatting is handled automatically.</>
      ),
      placeholder: "-----BEGIN CERTIFICATE----- …",
      error: Boolean(errors.SAML_IDP_CERTIFICATE),
      required: true,
    },
    {
      key: "SAML_PROVIDER_NAME",
      type: "text",
      label: "Provider name",
      description: <>Shown on the sign-in button, e.g. &quot;Continue with Okta&quot;.</>,
      placeholder: "Okta",
      error: Boolean(errors.SAML_PROVIDER_NAME),
      required: false,
    },
    {
      key: "SAML_ATTR_SUBJECT",
      type: "text",
      label: "Stable subject attribute (optional)",
      description: (
        <>Immutable directory/object identifier used for account binding. When empty, a non-transient NameID is used.</>
      ),
      placeholder: "object_id",
      error: Boolean(errors.SAML_ATTR_SUBJECT),
      required: false,
    },
    {
      key: "SAML_ATTR_EMAIL",
      type: "text",
      label: "Email attribute (optional)",
      description: <>Assertion attribute carrying the email. Common names and the NameID are tried automatically.</>,
      placeholder: "email",
      error: Boolean(errors.SAML_ATTR_EMAIL),
      required: false,
    },
    {
      key: "SAML_ATTR_FIRST_NAME",
      type: "text",
      label: "First-name attribute (optional)",
      description: <>Assertion attribute carrying the given name.</>,
      placeholder: "first_name",
      error: Boolean(errors.SAML_ATTR_FIRST_NAME),
      required: false,
    },
    {
      key: "SAML_ATTR_LAST_NAME",
      type: "text",
      label: "Last-name attribute (optional)",
      description: <>Assertion attribute carrying the family name.</>,
      placeholder: "last_name",
      error: Boolean(errors.SAML_ATTR_LAST_NAME),
      required: false,
    },
  ];

  const SAML_SERVICE_FIELD: TCopyField[] = [
    {
      key: "ACS_URL",
      label: "ACS URL (single sign-on URL)",
      url: `${originURL}/auth/saml/callback/`,
      description: (
        <>
          Paste this into your IdP&apos;s <CodeBlock darkerShade>ACS / Single sign-on URL</CodeBlock> field.
        </>
      ),
    },
    {
      key: "SP_Metadata_URL",
      label: "SP metadata URL",
      url: `${originURL}/auth/saml/metadata/`,
      description: (
        <>
          Most IdPs can import the service provider configuration from this metadata document. It is also the{" "}
          <CodeBlock darkerShade>SP entity ID / audience</CodeBlock>.
        </>
      ),
    },
  ];

  const onSubmit = async (formData: SAMLConfigFormValues) => {
    if (!isValidHttpsUrl(formData.SAML_IDP_SSO_URL)) {
      setError("SAML_IDP_SSO_URL", {
        type: "validate",
        message: "Enter a valid HTTPS URL without credentials or a fragment.",
      });
      return;
    }

    const payload: Partial<SAMLConfigFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Your SAML authentication is configured. You should test it now.",
      });
      reset({
        SAML_IDP_ENTITY_ID: response.find((item) => item.key === "SAML_IDP_ENTITY_ID")?.value,
        SAML_IDP_SSO_URL: response.find((item) => item.key === "SAML_IDP_SSO_URL")?.value,
        SAML_IDP_CERTIFICATE: response.find((item) => item.key === "SAML_IDP_CERTIFICATE")?.value,
        SAML_PROVIDER_NAME: response.find((item) => item.key === "SAML_PROVIDER_NAME")?.value,
        SAML_ATTR_EMAIL: response.find((item) => item.key === "SAML_ATTR_EMAIL")?.value,
        SAML_ATTR_FIRST_NAME: response.find((item) => item.key === "SAML_ATTR_FIRST_NAME")?.value,
        SAML_ATTR_LAST_NAME: response.find((item) => item.key === "SAML_ATTR_LAST_NAME")?.value,
        SAML_ATTR_SUBJECT: response.find((item) => item.key === "SAML_ATTR_SUBJECT")?.value,
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
            <div className="pt-2.5 text-18 font-medium">IdP-provided details for Hangar</div>
            {SAML_FORM_FIELDS.map((field) => (
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
          <div className="col-span-2 md:col-span-1">
            <div className="flex flex-col gap-y-4 rounded-lg bg-layer-1 px-6 pt-1.5 pb-4">
              <div className="pt-2 text-18 font-medium">Hangar-provided details for your IdP</div>
              {SAML_SERVICE_FIELD.map((field) => (
                <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
