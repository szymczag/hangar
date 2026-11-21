/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { observer } from "mobx-react";
import Link from "next/link";
import { useTheme } from "next-themes";
import useSWR from "swr";
// plane internal packages
import { Switch } from "@makeplane/propel/components/switch";
import { ChevronRightOutline } from "@makeplane/propel/icons";
import type { TInstanceConfigurationKeys, TInstanceAuthenticationModes } from "@plane/types";
import { cn, resolveGeneralTheme } from "@plane/utils";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
import { AuthenticationMethodCard } from "@/components/authentication/authentication-method-card";
import { Skeleton } from "@plane/blocks/skeleton";
import { setPromiseToast, setToast } from "@plane/blocks/toast";
// helpers
import { canDisableAuthMethod } from "@/helpers/authentication";
// hooks
import { useAuthenticationModes } from "@/hooks/oauth";
import { useInstance } from "@/hooks/store";
import { useConfigurationEditable } from "@/hooks/use-configuration-editable";
// types
import type { Route } from "./+types/page";

const InstanceAuthenticationPage = observer(function InstanceAuthenticationPage(_props: Route.ComponentProps) {
  // theme
  const { resolvedTheme: resolvedThemeAdmin } = useTheme();
  const resolvedTheme = resolveGeneralTheme(resolvedThemeAdmin);
  // Ref to store authentication modes for validation (avoids circular dependency)
  const authenticationModesRef = useRef<TInstanceAuthenticationModes[]>([]);
  // state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  // store hooks
  const { fetchInstanceConfigurations, formattedConfig, updateInstanceConfigurations } = useInstance();
  const isConfigurationEditable = useConfigurationEditable();
  // derived values
  const enableSignUpConfig = formattedConfig?.ENABLE_SIGNUP ?? "";

  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  // Create updateConfig with validation - uses authenticationModesRef for current modes
  const updateConfig = useCallback(
    (key: TInstanceConfigurationKeys, value: string): void => {
      // Check if trying to disable (value === "0")
      if (value === "0") {
        // Check if this key is an authentication method key
        const currentAuthModes = authenticationModesRef.current;
        const isAuthMethodKey = currentAuthModes.some((method) => method.enabledConfigKey === key);

        // Only validate if this is an authentication method key
        if (isAuthMethodKey) {
          const canDisable = canDisableAuthMethod(key, currentAuthModes, formattedConfig);

          if (!canDisable) {
            setToast({
              type: "error",
              title: "Cannot disable authentication",
              message:
                "At least one authentication method must remain enabled. Please enable another method before disabling this one.",
            });
            return;
          }
        }
      }

      // Proceed with the update
      setIsSubmitting(true);

      const payload = {
        [key]: value,
      };

      const updateConfigPromise = updateInstanceConfigurations(payload);

      setPromiseToast(updateConfigPromise, {
        loading: "Saving configuration",
        success: {
          title: "Success",
          message: () => "Configuration saved successfully",
        },
        error: {
          title: "Error",
          message: () => "Failed to save configuration",
        },
      });

      void updateConfigPromise
        .then(() => {
          setIsSubmitting(false);
          return undefined;
        })
        .catch(() => {
          setIsSubmitting(false);
        });
    },
    [formattedConfig, updateInstanceConfigurations]
  );

  // Get authentication modes - this will use updateConfig which includes validation
  const authenticationModes = useAuthenticationModes({
    disabled: isSubmitting,
    updateConfig,
    resolvedTheme,
  });

  // Update ref with latest authentication modes (updateConfig reads it only from event handlers)
  useEffect(() => {
    authenticationModesRef.current = authenticationModes;
  }, [authenticationModes]);

  return (
    <PageWrapper
      header={{
        title: "Manage authentication modes for your instance",
        description: "Configure authentication modes for your team and restrict sign-ups to be invite only.",
      }}
    >
      {formattedConfig ? (
        <div className="space-y-3">
          <div className="flex w-full items-start justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 md:items-center md:gap-8">
            <div className="flex min-w-0 grow items-center gap-4">
              <div className="min-w-0 grow">
                <div className="pb-1 text-body-sm-medium text-primary">
                  Allow anyone to sign up even without an invite
                </div>
                <div className="text-body-xs-regular leading-5 text-tertiary">
                  Leaving this on lets anyone who can reach this instance create an account. They join no workspace and
                  see no content until invited, but they can sign in and create their own workspace unless that is also
                  disabled. Toggling it off requires an invitation to sign up.
                </div>
              </div>
            </div>
            <div className={cn("shrink-0", { "opacity-70": isSubmitting })}>
              <div className="flex items-center gap-4">
                <Switch
                  aria-label="Allow anyone to sign up even without an invite"
                  checked={Boolean(parseInt(enableSignUpConfig))}
                  onCheckedChange={() => {
                    if (Boolean(parseInt(enableSignUpConfig)) === true) {
                      updateConfig("ENABLE_SIGNUP", "0");
                    } else {
                      updateConfig("ENABLE_SIGNUP", "1");
                    }
                  }}
                  size="sm"
                  disabled={isSubmitting || !isConfigurationEditable}
                />
              </div>
            </div>
          </div>
          <h3 className="pt-3 text-h6-medium text-primary">Domain policy</h3>
          <Link
            href="/authentication/domains"
            className="flex w-full items-center justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 hover:bg-layer-2-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent-strong focus-visible:outline-solid md:gap-8"
          >
            <div className="min-w-0 grow">
              <div className="pb-1 text-body-sm-medium text-primary">Pin email domains to a provider</div>
              <div className="text-body-xs-regular leading-5 text-tertiary">
                Decide which provider owns each domain, so nobody can claim a colleague&apos;s address through a weaker
                sign-in method, and choose the workspace its users join automatically.
              </div>
            </div>
            <ChevronRightOutline className="size-4 shrink-0 text-tertiary" aria-hidden="true" />
          </Link>
          <Link
            href="/authentication/identity-import"
            className="flex w-full items-center justify-between gap-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 hover:bg-layer-2-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent-strong focus-visible:outline-solid md:gap-8"
          >
            <div className="min-w-0 grow">
              <div className="pb-1 text-body-sm-medium text-primary">Import identities for existing accounts</div>
              <div className="text-body-xs-regular leading-5 text-tertiary">
                Link the accounts you already have to the subjects your provider asserts, so pinning a domain does not
                lock them out. Requires your password at the point of use.
              </div>
            </div>
            <ChevronRightOutline className="size-4 shrink-0 text-tertiary" aria-hidden="true" />
          </Link>
          <h3 className="pt-3 text-h6-medium text-primary">Available authentication modes</h3>
          {authenticationModes.map((method) => (
            <AuthenticationMethodCard
              key={method.key}
              name={method.name}
              description={method.description}
              icon={method.icon}
              config={method.config}
              disabled={isSubmitting}
              unavailable={method.unavailable}
            />
          ))}
        </div>
      ) : (
        <Skeleton className="space-y-10">
          <Skeleton.Item height="50px" width="75%" />
          <Skeleton.Item height="50px" width="75%" />
          <Skeleton.Item height="50px" width="40%" />
          <Skeleton.Item height="50px" width="40%" />
          <Skeleton.Item height="50px" width="20%" />
        </Skeleton>
      )}
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "Authentication Settings - Hangar Web" }];

export default InstanceAuthenticationPage;
