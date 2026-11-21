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

const isValidHttpsUrl = (value: string | undefined) => {
  if (!value) return false;

  try {
    const url = new URL(value);
    return url.protocol === "https:" && Boolean(url.hostname) && !url.username && !url.password && !url.hash;
  } catch {
    return false;
  }
};

export const SAMLConfiguration = observer(function SAMLConfiguration(props: Props) {
  const { disabled, updateConfig } = props;
  // store
  const { formattedConfig } = useInstance();
  // derived values
  const samlConfig = formattedConfig?.IS_SAML_ENABLED ?? "";
  const samlConfigured =
    !!formattedConfig?.SAML_IDP_ENTITY_ID &&
    isValidHttpsUrl(formattedConfig?.SAML_IDP_SSO_URL) &&
    !!formattedConfig?.SAML_IDP_CERTIFICATE;

  return (
    <>
      {samlConfigured ? (
        <div className="flex items-center gap-4">
          <AnchorButton variant="primary" size="sm" render={<Link href="/authentication/saml" />} label="Edit" />
          <Switch
            aria-label="Enable SAML"
            checked={Boolean(parseInt(samlConfig))}
            onCheckedChange={() => {
              updateConfig("IS_SAML_ENABLED", parseInt(samlConfig) ? "0" : "1");
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
          render={<Link href="/authentication/saml" />}
          icon={<Icon icon={PreferencesOutline} tint="tertiary" />}
          label="Configure"
        />
      )}
    </>
  );
});
