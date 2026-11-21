/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
// icons
import { UpdatesOutline } from "@makeplane/propel/icons";
// plane internal packages
import { InstanceMaintenanceService } from "@plane/services";
import type { TMaintenanceNoticeAdmin } from "@plane/services";
import { Skeleton } from "@plane/blocks/skeleton";
// components
import { AuthenticationMethodCard } from "@/components/authentication/authentication-method-card";
import { PageWrapper } from "@/components/common/page-wrapper";
// local
import { InstanceMaintenanceForm } from "./form";

const maintenanceService = new InstanceMaintenanceService();

export default function InstanceMaintenancePage() {
  const [saved, setSaved] = useState<TMaintenanceNoticeAdmin | undefined>(undefined);

  const { data } = useSWR("INSTANCE_MAINTENANCE_ADMIN", () => maintenanceService.retrieveForAdmin(), {
    revalidateOnFocus: false,
  });

  const notice = saved ?? data;

  return (
    <PageWrapper
      customHeader={
        <AuthenticationMethodCard
          name="Maintenance notice"
          description="Announce planned downtime, or say something is wrong, in a strip above the whole application."
          icon={<UpdatesOutline className="size-6 p-0.5 text-tertiary" />}
          config={<></>}
          disabled={!notice}
          withBorder={false}
        />
      }
    >
      {notice ? (
        <InstanceMaintenanceForm notice={notice} onSaved={setSaved} />
      ) : (
        <Skeleton className="space-y-8">
          <Skeleton.Item height="90px" />
          <Skeleton.Item height="70px" />
          <Skeleton.Item height="50px" width="40%" />
        </Skeleton>
      )}
    </PageWrapper>
  );
}
