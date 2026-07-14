/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
// components
import { PageWrapper } from "@/components/common/page-wrapper";
// hooks
import { useInstance } from "@/hooks/store";
// local imports
import { GeneralConfigurationForm } from "./form";
// types
import type { Route } from "./+types/page";

function GeneralPage() {
  const { fetchTelemetryConfiguration, instance, instanceAdmins, telemetryConfiguration } = useInstance();
  useSWR("INSTANCE_TELEMETRY_CONFIGURATION", () => fetchTelemetryConfiguration());

  return (
    <PageWrapper
      header={{
        title: "General settings",
        description:
          "Change the name of your instance and instance admin e-mail addresses. Enable or disable telemetry in your instance.",
      }}
    >
      {instance && instanceAdmins && telemetryConfiguration && (
        <GeneralConfigurationForm
          instance={instance}
          instanceAdmins={instanceAdmins}
          telemetryConfiguration={telemetryConfiguration}
        />
      )}
    </PageWrapper>
  );
}

export const meta: Route.MetaFunction = () => [{ title: "General Settings - God Mode" }];

export default observer(GeneralPage);
