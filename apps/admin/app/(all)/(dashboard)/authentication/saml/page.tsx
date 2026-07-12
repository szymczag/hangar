/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// icons
import { ShieldCheck } from "lucide-react";
// plane internal packages
import { setPromiseToast } from "@plane/propel/toast";
import { Loader, ToggleSwitch } from "@plane/ui";
// components
import { AuthenticationMethodCard } from "@/components/authentication/authentication-method-card";
import { PageWrapper } from "@/components/common/page-wrapper";
// hooks
import { useInstance } from "@/hooks/store";
// types
import type { Route } from "./+types/page";
// local
import { InstanceSAMLConfigForm } from "./form";

const isValidHttpsUrl = (value: string | undefined) => {
  if (!value) return false;

  try {
    const url = new URL(value);
    return url.protocol === "https:" && Boolean(url.hostname) && !url.username && !url.password && !url.hash;
  } catch {
    return false;
  }
};

const InstanceSAMLAuthenticationPage = observer(function InstanceSAMLAuthenticationPage() {
  // store
  const { fetchInstanceConfigurations, formattedConfig, updateInstanceConfigurations } = useInstance();
  // state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  // config
  const enableSAMLConfig = formattedConfig?.IS_SAML_ENABLED ?? "";
  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  const updateConfig = async (key: "IS_SAML_ENABLED", value: string) => {
    setIsSubmitting(true);

    const payload = {
      [key]: value,
    };

    const updateConfigPromise = updateInstanceConfigurations(payload);

    setPromiseToast(updateConfigPromise, {
      loading: "Saving Configuration",
      success: {
        title: "Configuration saved",
        message: () => `SAML authentication is now ${value === "1" ? "active" : "disabled"}.`,
      },
      error: {
        title: "Error",
        message: () => "Failed to save configuration",
      },
    });

    try {
      await updateConfigPromise;
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const isSAMLEnabled = enableSAMLConfig === "1";
  const isSAMLConfigured =
    Boolean(formattedConfig?.SAML_IDP_ENTITY_ID) &&
    isValidHttpsUrl(formattedConfig?.SAML_IDP_SSO_URL) &&
    Boolean(formattedConfig?.SAML_IDP_CERTIFICATE);

  return (
    <PageWrapper
      customHeader={
        <AuthenticationMethodCard
          name="SAML 2.0"
          description="Allow members to log in or sign up through your SAML 2.0 identity provider."
          icon={<ShieldCheck className="h-6 w-6 p-0.5 text-tertiary" />}
          config={
            <ToggleSwitch
              value={isSAMLEnabled}
              onChange={() => {
                updateConfig("IS_SAML_ENABLED", isSAMLEnabled ? "0" : "1");
              }}
              size="sm"
              disabled={isSubmitting || !formattedConfig || (!isSAMLEnabled && !isSAMLConfigured)}
            />
          }
          disabled={isSubmitting || !formattedConfig}
          withBorder={false}
        />
      }
    >
      {formattedConfig ? (
        <InstanceSAMLConfigForm config={formattedConfig} />
      ) : (
        <Loader className="space-y-8">
          <Loader.Item height="50px" width="25%" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" width="50%" />
        </Loader>
      )}
    </PageWrapper>
  );
});
export const meta: Route.MetaFunction = () => [{ title: "SAML Authentication - God Mode" }];

export default InstanceSAMLAuthenticationPage;
