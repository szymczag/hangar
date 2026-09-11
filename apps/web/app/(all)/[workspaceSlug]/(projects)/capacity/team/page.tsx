/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import { useUserPermissions } from "@/hooks/store/user";
import { CapacityService } from "@/services/capacity.service";
import type { Route } from "./+types/page";
import { ScheduleEditor } from "../shared/schedule-editor";
import { useCapacityData } from "../shared/use-capacity-data";
import { CapacityLedger } from "./capacity-ledger";

const capacityService = new CapacityService();

/**
 * Who has time this week, and how it is already booked.
 *
 * Two things differ deliberately from the combined page this is replacing.
 *
 * Opting in as a trainer is not offered here. It is a personal action that only
 * looked at home in the ledger's header because there was nowhere else for it to
 * be; it belongs on `/capacity`, and the empty state points there.
 *
 * Editing a schedule is admin-only and opens over the page rather than pushing
 * the whole ledger down, which is what the inline editor used to do on a long
 * trainer list. A trainer editing their own hours does that on `/capacity`.
 */
export default function TeamCapacityPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const { allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);

  const data = useCapacityData(workspaceSlug, featureEnabled);
  const [editingTrainerId, setEditingTrainerId] = useState<string | null>(null);

  const { data: ownProfile, mutate: mutateOwnProfile } = useSWR(
    featureEnabled ? ["capacity-trainer-self", workspaceSlug] : null,
    () => capacityService.getOwnTrainerProfile(workspaceSlug)
  );

  // Only an admin edits from here, so resolve against the trainer list alone --
  // the combined page also had to consider the viewer's own profile, because the
  // same state served the self-edit path.
  const editingProfile = data.trainers?.find((trainer) => trainer.user_id === editingTrainerId);

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <div className="h-full overflow-y-auto bg-surface-2">
      <PageHead title="Team capacity" />
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 p-4 md:p-6">
        <CapacityLedger
          data={data}
          isAdmin={isAdmin}
          ownProfile={ownProfile}
          onManageSchedule={(trainerId) => isAdmin && setEditingTrainerId(trainerId)}
          becomeTrainer={null}
        />

        {isAdmin && editingProfile ? (
          <section
            aria-label={`Manage ${editingProfile.display_name}`}
            className="flex flex-col gap-4 rounded-xl border border-subtle bg-surface-1 p-5"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-body-sm-medium">Managing {editingProfile.display_name}</h2>
              <Button variant="secondary" size="sm" onClick={() => setEditingTrainerId(null)}>
                Close
              </Button>
            </div>
            <ScheduleEditor
              key={`${editingProfile.id}-${editingProfile.schedule_revision}-schedule`}
              profile={editingProfile}
              workspaceSlug={workspaceSlug}
              onSaved={async () => {
                await Promise.all([data.mutateTrainers(), mutateOwnProfile()]);
                await data.refreshCapacity();
              }}
            />
          </section>
        ) : null}
      </div>
    </div>
  );
}
