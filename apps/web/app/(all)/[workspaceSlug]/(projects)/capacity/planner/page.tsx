/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Spinner } from "@plane/ui";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import type { Route } from "./+types/page";
import { useCapacityData } from "../shared/use-capacity-data";
import { WorkshopPlanner } from "./workshop-planner";

/**
 * Workshop planning: what needs to happen, who can deliver it, and when.
 *
 * The planner reads the same `GET /capacity/` response the team ledger renders
 * -- it derives candidate slots from those intervals rather than asking the
 * server for them. Calling `useCapacityData` here composes the same SWR key the
 * ledger does, so the two routes share one request rather than doubling it.
 */
export default function WorkshopPlannerPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const { capacity, capacityLoading, weekStart, weekEnd } = useCapacityData(workspaceSlug, featureEnabled);

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <div className="h-full overflow-y-auto bg-surface-2">
      <PageHead title="Workshop planner" />
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 p-4 md:p-6">
        {capacity?.trainers.length ? (
          <WorkshopPlanner
            workspaceSlug={workspaceSlug}
            trainers={capacity.trainers}
            weekStart={weekStart}
            weekEnd={weekEnd}
          />
        ) : capacityLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner />
          </div>
        ) : (
          <section className="rounded-xl border border-subtle bg-surface-1 p-6">
            <h1 className="text-body-sm-medium text-primary">No trainers to plan around yet.</h1>
            <p className="mt-1 text-body-xs-regular text-secondary">
              The planner works from trainer availability. Opt in on your own capacity page, or ask a colleague to.
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
