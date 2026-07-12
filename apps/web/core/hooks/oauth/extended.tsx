/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): upstream ships this hook returning no options; it is the
// designated seam for extended sign-in methods.

// plane imports
import { useSearchParams } from "next/navigation";
import { KeyRound } from "lucide-react";
import { API_BASE_URL } from "@plane/constants";
import type { TOAuthConfigs, TOAuthOption } from "@plane/types";
// hooks
import { useInstance } from "@/hooks/store/use-instance";

export const useExtendedOAuthConfig = (oauthActionText: string): TOAuthConfigs => {
  // router
  const searchParams = useSearchParams();
  // query params
  const nextPath = searchParams.get("next_path");
  // store hooks
  const { config } = useInstance();
  // derived values
  const providerName = config?.oidc_provider_name || "OIDC";
  const oAuthOptions: TOAuthOption[] = [
    {
      id: "oidc",
      text: `${oauthActionText} with ${providerName}`,
      icon: <KeyRound className="h-[18px] w-[18px]" />,
      onClick: () => {
        const params = new URLSearchParams();
        if (nextPath) params.set("next_path", nextPath);
        const query = params.toString();
        window.location.assign(`${API_BASE_URL}/auth/oidc/${query ? `?${query}` : ""}`);
      },
      enabled: config?.is_oidc_enabled,
    },
  ];

  return {
    isOAuthEnabled: config?.is_oidc_enabled || false,
    oAuthOptions,
  };
};
