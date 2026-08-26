/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane internal packages
import { setPromiseToast } from "@plane/propel/toast";
import { Loader, ToggleSwitch } from "@plane/ui";
// assets
import giteaLogo from "@/app/assets/logos/gitea-logo.svg?url";
// components
import { AuthenticationMethodCard } from "@/components/authentication/authentication-method-card";
import { PageWrapper } from "@/components/common/page-wrapper";
// hooks
import { configurationErrorMessage } from "@/helpers/configuration-error";
import { useInstance } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";
// types
import type { Route } from "./+types/page";
// local
import { InstanceGiteaConfigForm } from "./form";

const InstanceGiteaAuthenticationPage = observer(function InstanceGiteaAuthenticationPage() {
  // store
  const { fetchInstanceConfigurations, formattedConfig, updateInstanceConfigurations } = useInstance();
  const isConfigurationEditable = useConfigurationEditable();
  // state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  // config
  const enableGiteaConfig = formattedConfig?.IS_GITEA_ENABLED ?? "";
  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  const updateConfig = async (key: "IS_GITEA_ENABLED", value: string) => {
    setIsSubmitting(true);

    const payload = {
      [key]: value,
    };

    const updateConfigPromise = updateInstanceConfigurations(payload);

    setPromiseToast(updateConfigPromise, {
      loading: "Saving Configuration",
      success: {
        title: "Configuration saved",
        message: () => `Gitea authentication is now ${value === "1" ? "active" : "disabled"}.`,
      },
      error: {
        title: "Error",
        message: (error) => configurationErrorMessage(error),
      },
    });

    try {
      await updateConfigPromise;
    } catch {
      // The toast above reports the reason; this only clears the spinner.
    } finally {
      setIsSubmitting(false);
    }
  };

  const isGiteaEnabled = enableGiteaConfig === "1";

  return (
    <PageWrapper
      customHeader={
        <AuthenticationMethodCard
          name="Gitea"
          description="Allow members to login or sign up to plane with their Gitea accounts."
          icon={<img src={giteaLogo} height={24} width={24} alt="Gitea Logo" />}
          config={
            <ToggleSwitch
              value={isGiteaEnabled}
              onChange={() => {
                updateConfig("IS_GITEA_ENABLED", isGiteaEnabled ? "0" : "1");
              }}
              size="sm"
              disabled={isSubmitting || !formattedConfig || !isConfigurationEditable}
            />
          }
          disabled={isSubmitting || !formattedConfig}
          withBorder={false}
        />
      }
    >
      {formattedConfig ? (
        <InstanceGiteaConfigForm config={formattedConfig} />
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
export const meta: Route.MetaFunction = () => [{ title: "Gitea Authentication - God Mode" }];

export default InstanceGiteaAuthenticationPage;
