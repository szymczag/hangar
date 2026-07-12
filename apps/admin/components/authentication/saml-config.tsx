/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
// icons
import { Settings2 } from "lucide-react";
// plane internal packages
import { getButtonStyling } from "@plane/propel/button";
import type { TInstanceAuthenticationMethodKeys } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useInstance } from "@/hooks/store";

type Props = {
  disabled: boolean;
  updateConfig: (key: TInstanceAuthenticationMethodKeys, value: string) => void;
};

export const SAMLConfiguration = observer(function SAMLConfiguration(props: Props) {
  const { disabled, updateConfig } = props;
  // store
  const { formattedConfig } = useInstance();
  // derived values
  const samlConfig = formattedConfig?.IS_SAML_ENABLED ?? "";
  const samlConfigured =
    !!formattedConfig?.SAML_IDP_ENTITY_ID &&
    !!formattedConfig?.SAML_IDP_SSO_URL &&
    !!formattedConfig?.SAML_IDP_CERTIFICATE;

  return (
    <>
      {samlConfigured ? (
        <div className="flex items-center gap-4">
          <Link href="/authentication/saml" className={cn(getButtonStyling("link", "base"), "font-medium")}>
            Edit
          </Link>
          <ToggleSwitch
            value={Boolean(parseInt(samlConfig))}
            onChange={() => {
              updateConfig("IS_SAML_ENABLED", parseInt(samlConfig) ? "0" : "1");
            }}
            size="sm"
            disabled={disabled}
          />
        </div>
      ) : (
        <Link href="/authentication/saml" className={cn(getButtonStyling("secondary", "base"), "text-tertiary")}>
          <Settings2 className="h-4 w-4 p-0.5 text-tertiary" />
          Configure
        </Link>
      )}
    </>
  );
});
