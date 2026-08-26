/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useInstance } from "@/hooks/store";

/**
 * Whether settings saved in this panel are the ones the instance reads.
 *
 * With `SKIP_ENV_VAR=0` the deployment's environment decides and stored values
 * are never read back, so the API refuses to save. Controls that stay
 * interactive in that mode invite a click that can only fail — the banner
 * explains the situation, but only to someone who reads it before reaching for
 * the switch.
 */
export function useConfigurationEditable(): boolean {
  const { formattedConfig } = useInstance();
  return formattedConfig?.CONFIGURATION_SOURCE !== "environment";
}
