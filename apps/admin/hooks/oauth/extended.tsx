/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): extended authentication modes merged into the list in
// ./index.ts alongside upstream's core map.

import { KeyRound } from "lucide-react";
// types
import type {
  TExtendedInstanceAuthenticationModeKeys,
  TGetBaseAuthenticationModeProps,
  TInstanceAuthenticationModes,
} from "@plane/types";
// components
import { OIDCConfiguration } from "@/components/authentication/oidc-config";

export const getExtendedAuthenticationModesMap: (
  props: TGetBaseAuthenticationModeProps
) => Record<TExtendedInstanceAuthenticationModeKeys, TInstanceAuthenticationModes> = ({ disabled, updateConfig }) => ({
  oidc: {
    key: "oidc",
    name: "OIDC",
    description: "Allow members to log in or sign up with any OpenID Connect identity provider.",
    icon: <KeyRound className="h-6 w-6 p-0.5 text-tertiary" />,
    config: <OIDCConfiguration disabled={disabled} updateConfig={updateConfig} />,
    enabledConfigKey: "IS_OIDC_ENABLED",
  },
});
