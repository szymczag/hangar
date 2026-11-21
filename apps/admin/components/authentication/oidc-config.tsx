/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
// icons
import { PreferencesOutline } from "@makeplane/propel/icons";
// plane internal packages
import { AnchorButton } from "@makeplane/propel/components/anchor-button";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { Switch } from "@makeplane/propel/components/switch";
import type { TInstanceAuthenticationMethodKeys } from "@plane/types";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  disabled: boolean;
  updateConfig: (key: TInstanceAuthenticationMethodKeys, value: string) => void;
};

export const OIDCConfiguration = observer(function OIDCConfiguration(props: Props) {
  const { disabled, updateConfig } = props;
  // store
  const { formattedConfig } = useInstance();
  // derived values
  const oidcConfig = formattedConfig?.IS_OIDC_ENABLED ?? "";
  const oidcConfigured =
    !!formattedConfig?.OIDC_ISSUER && !!formattedConfig?.OIDC_CLIENT_ID && !!formattedConfig?.OIDC_CLIENT_SECRET;

  return (
    <>
      {oidcConfigured ? (
        <div className="flex items-center gap-4">
          <AnchorButton variant="primary" size="sm" render={<Link href="/authentication/oidc" />} label="Edit" />
          <Switch
            aria-label="Enable OIDC"
            checked={Boolean(parseInt(oidcConfig))}
            onCheckedChange={() => {
              updateConfig("IS_OIDC_ENABLED", parseInt(oidcConfig) ? "0" : "1");
            }}
            size="sm"
            disabled={disabled}
          />
        </div>
      ) : (
        <Button
          variant="secondary"
          size="sm"
          stretch="auto"
          nativeButton={false}
          render={<Link href="/authentication/oidc" />}
          icon={<Icon icon={PreferencesOutline} tint="tertiary" />}
          label="Configure"
        />
      )}
    </>
  );
});
