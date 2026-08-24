/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
// plane internal packages
import Link from "next/link";
// plane internal packages
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceSSODomainPolicyConfigurationKeys } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

type DomainPolicyFormValues = Record<TInstanceSSODomainPolicyConfigurationKeys, string>;

export function InstanceSSODomainPolicyForm(props: Props) {
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
  } = useForm<DomainPolicyFormValues>({
    defaultValues: {
      SSO_ENFORCED_DOMAINS: config["SSO_ENFORCED_DOMAINS"] ?? "",
      SSO_AUTO_JOIN_WORKSPACES: config["SSO_AUTO_JOIN_WORKSPACES"] ?? "",
    },
  });

  const DOMAIN_POLICY_FORM_FIELDS: TControllerInputFormField<DomainPolicyFormValues>[] = [
    {
      key: "SSO_ENFORCED_DOMAINS",
      type: "text",
      label: "Domains pinned to a provider",
      description: (
        <>
          Comma-separated. <CodeBlock darkerShade>corp.com=google</CodeBlock> lets only Google sign in people at that
          domain; <CodeBlock darkerShade>corp.com=oidc;saml</CodeBlock> allows either; a bare{" "}
          <CodeBlock darkerShade>corp.com</CodeBlock> allows any federated provider. Every other method — password,
          magic code, and the other providers — is refused for a listed domain, on both sign-up and sign-in, so nobody
          can claim a colleague&apos;s address through a weaker route. Matching is exact: list subdomains separately.
        </>
      ),
      placeholder: "corp.com=google, eu.corp.com=saml",
      error: Boolean(errors.SSO_ENFORCED_DOMAINS),
      required: false,
    },
    {
      key: "SSO_AUTO_JOIN_WORKSPACES",
      type: "text",
      label: "Workspace to join on sign-in",
      description: (
        <>
          Comma-separated <CodeBlock darkerShade>domain=workspace-slug:role</CodeBlock> entries, where role is{" "}
          <CodeBlock darkerShade>admin</CodeBlock>, <CodeBlock darkerShade>member</CodeBlock> or{" "}
          <CodeBlock darkerShade>guest</CodeBlock> (guest if omitted). Leave empty to keep inviting people by hand. Only
          applies to domains pinned above — membership is granted on an email domain, so that domain has to belong to
          one provider first. An existing membership is never changed, so a role you lowered by hand stays lowered.
        </>
      ),
      placeholder: "corp.com=engineering:member",
      error: Boolean(errors.SSO_AUTO_JOIN_WORKSPACES),
      required: false,
    },
  ];

  const onSubmit = async (formData: DomainPolicyFormValues) => {
    const payload: Partial<DomainPolicyFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: "Domain policy saved. Test a sign-in from a pinned domain now.",
      });
      reset({
        SSO_ENFORCED_DOMAINS: response.find((item) => item.key === "SSO_ENFORCED_DOMAINS")?.value,
        SSO_AUTO_JOIN_WORKSPACES: response.find((item) => item.key === "SSO_AUTO_JOIN_WORKSPACES")?.value,
      });
    } catch (error) {
      console.error(error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error!",
        message: "Something went wrong. Please try again.",
      });
    }
  };

  const handleGoBack = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (isDirty) {
      event.preventDefault();
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
      <div className="space-y-8">
        <div className="grid grid-cols-1 gap-x-12 gap-y-8 lg:grid-cols-2">
          <div className="col-span-2 flex flex-col gap-y-4 md:col-span-1">
            {DOMAIN_POLICY_FORM_FIELDS.map((field) => (
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
                <Button variant="primary" onClick={handleSubmit(onSubmit)} loading={isSubmitting} disabled={!isDirty}>
                  {isSubmitting ? "Saving..." : "Save changes"}
                </Button>
                <Link href="/authentication" className={getButtonStyling("secondary", "lg")} onClick={handleGoBack}>
                  Go back
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
