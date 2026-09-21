/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { useInstance } from "@/hooks/store/use-instance";
import { CapacityService } from "@/services/capacity.service";

const capacityService = new CapacityService();

/**
 * Whether this project holds training.
 *
 * The Workshop type used to arrive in every project as soon as anybody in the
 * workspace became a trainer, which put a training-specific type in the picker of
 * projects with nothing to do with training. A project now opts in here, and only
 * its administrators decide.
 *
 * Turning it off is refused while the project holds a Workshop, and the button
 * says so before anybody presses it rather than after: those Workshops would be
 * left as work items of a type their own project no longer offers.
 */
export function WorkshopsCard({
  workspaceSlug,
  projectId,
  isAdmin,
  onChanged,
}: {
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
  onChanged: () => void;
}) {
  const { config } = useInstance();
  const capacityEnabled = config?.is_google_calendar_capacity_enabled === true;
  const [busy, setBusy] = useState(false);
  const { data, mutate } = useSWR(capacityEnabled ? ["project-workshops", workspaceSlug, projectId] : null, () =>
    capacityService.getProjectWorkshops(workspaceSlug, projectId)
  );

  if (!capacityEnabled || !data) return null;

  const inUse = data.workshop_count > 0;

  const toggle = async (enabled: boolean) => {
    setBusy(true);
    try {
      await mutate(await capacityService.setProjectWorkshops(workspaceSlug, projectId, enabled), false);
      onChanged();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: enabled ? "Workshops enabled" : "Workshops turned off",
        message: enabled
          ? "Workshops can now be created and imported in this project."
          : "This project no longer offers the Workshop type.",
      });
    } catch (cause) {
      const message =
        cause && typeof cause === "object" && "error" in cause && typeof cause.error === "string"
          ? cause.error
          : "Try again.";
      setToast({ type: TOAST_TYPE.ERROR, title: "Could not change Workshops", message });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-subtle p-4">
      <div>
        <p className="text-14 font-medium">Workshops {data.enabled ? "are enabled" : "are not enabled"}</p>
        <p className="text-13 text-tertiary">
          {data.enabled
            ? inUse
              ? `This project holds ${data.workshop_count} Workshop${data.workshop_count === 1 ? "" : "s"}, so the type cannot be turned off until they are moved or retyped.`
              : "This project offers the Workshop type, for training planned and imported here."
            : "Turn them on if this project holds training. Only projects that do offer the Workshop type."}
        </p>
      </div>
      {isAdmin &&
        (data.enabled ? (
          <Button variant="secondary" size="sm" disabled={busy || inUse} onClick={() => void toggle(false)}>
            Turn off
          </Button>
        ) : (
          <Button variant="primary" size="sm" disabled={busy} onClick={() => void toggle(true)}>
            {busy ? "Enabling…" : "Enable Workshops"}
          </Button>
        ))}
    </div>
  );
}
