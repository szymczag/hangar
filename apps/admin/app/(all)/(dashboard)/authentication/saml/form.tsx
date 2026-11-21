/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isEmpty } from "lodash-es";
import { useForm } from "react-hook-form";
// plane internal packages
import { setToast } from "@plane/blocks/toast";
import { API_BASE_URL } from "@plane/constants";
import type { IFormattedInstanceConfiguration, TInstanceSAMLAuthenticationConfigurationKeys } from "@plane/types";
// components
import { OAuthProviderForm } from "@/components/authentication/oauth-provider-form";
import { CodeBlock } from "@/components/common/code-block";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import type { TCopyField } from "@/components/common/copy-field";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";
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
  // store hooks
  const { updateInstanceConfigurations } = useInstance();
  // form data
  // SAML has no secret: the IdP certificate is public. It keeps its own form
  // state for the SSO URL check, and renders through the shared provider form.
  const {
    handleSubmit,
    control,
    reset,
    setError,
    formState: { errors },
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

  const SAML_FORM_FIELDS: TControllerInputFormField<SAMLConfigFormValues>[] = [
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
      await updateInstanceConfigurations(payload);
      setToast({
        type: "success",
        title: "Done!",
        message: "Your SAML authentication is configured. You should test it now.",
      });
      // the submitted values become the new baseline, so Save disables again until the next edit
      reset(formData);
    } catch (error) {
      setToast({ type: "error", title: "Error", message: configurationErrorMessage(error) });
    }
  };

  return (
    <OAuthProviderForm
      providerName="IdP"
      recipientName="your IdP"
      control={control}
      formFields={SAML_FORM_FIELDS}
      onSave={handleSubmit(onSubmit)}
      serviceDetails={SAML_SERVICE_FIELD}
    />
  );
}
