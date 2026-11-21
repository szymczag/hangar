/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// plane internal packages
import { Banner } from "@makeplane/propel/components/banner";
import { LockOutline } from "@makeplane/propel/icons";
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
    <div className="mx-auto w-full max-w-[1000px] shrink-0 px-4 pt-6 md:px-8 2xl:max-w-[1200px]">
      <Banner
        placement="inline"
        variant="warning"
        icon={<LockOutline />}
        title="Settings on this instance come from environment variables"
        description={
          <>
            This deployment runs with <span className="font-mono">SKIP_ENV_VAR=0</span>, so values saved here are never
            read back and saving is refused. Change the deployment environment instead, or remove that variable to
            manage configuration from this panel.
          </>
        }
      />
    </div>
  );
});
