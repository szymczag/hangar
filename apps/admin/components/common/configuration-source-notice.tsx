/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// icons
import { Lock } from "lucide-react";
// plane internal packages
import { cn } from "@plane/utils";
// hooks
import { useInstance } from "@/hooks/store";

/**
 * Warns when this instance reads its configuration from environment variables.
 *
 * In that mode the forms below still render and still submit, but nothing they
 * save is ever read back, so an admin would be left believing a change had
 * taken effect. The API refuses those writes; this explains why before anyone
 * tries.
 */
export const ConfigurationSourceNotice = observer(function ConfigurationSourceNotice() {
  const { fetchInstanceConfigurations, formattedConfig } = useInstance();

  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  if (formattedConfig?.CONFIGURATION_SOURCE !== "environment") return null;

  return (
    <div
      className={cn(
        "border-amber-500/40 bg-amber-500/10 mx-auto mt-6 flex max-w-6xl items-start gap-3 rounded-sm border px-4 py-3"
      )}
    >
      <Lock className="text-amber-600 mt-0.5 h-4 w-4 shrink-0" />
      <div className="text-13 leading-5">
        <div className="font-medium">Settings on this instance come from environment variables</div>
        <div className="text-tertiary">
          This deployment runs with <span className="font-mono">SKIP_ENV_VAR=0</span>, so values saved here are never
          read back and saving is refused. Change the deployment environment instead, or remove that variable to manage
          configuration from this panel.
        </div>
      </div>
    </div>
  );
});
