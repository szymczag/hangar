/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CalendarClock } from "lucide-react";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import { CapacityService, type TWorkshopSchedule } from "@/services/capacity.service";

const capacityService = new CapacityService();

const localValue = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueTypeId: string | null;
  isEditable: boolean;
};

export function WorkshopScheduleProperty({ workspaceSlug, projectId, issueId, issueTypeId, isEditable }: Props) {
  const { getTypeById } = useIssueTypes(workspaceSlug, projectId);
  const isWorkshop = getTypeById(issueTypeId)?.system_key === "workshop";
  const { data, mutate } = useSWR<TWorkshopSchedule | null>(
    isWorkshop ? ["workshop-schedule", workspaceSlug, projectId, issueId] : null,
    async () => {
      try {
        return await capacityService.getWorkshopSchedule(workspaceSlug, projectId, issueId);
      } catch {
        return null;
      }
    }
  );
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [preparationMinutes, setPreparationMinutes] = useState(0);
  const [travelBeforeMinutes, setTravelBeforeMinutes] = useState(0);
  const [travelAfterMinutes, setTravelAfterMinutes] = useState(0);
  const [saving, setSaving] = useState(false);
  const viewerTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  useEffect(() => {
    setStartsAt(localValue(data?.starts_at));
    setEndsAt(localValue(data?.ends_at));
    setPreparationMinutes(data?.preparation_minutes ?? 0);
    setTravelBeforeMinutes(data?.travel_before_minutes ?? 0);
    setTravelAfterMinutes(data?.travel_after_minutes ?? 0);
  }, [data]);

  if (!isWorkshop) return null;

  const save = async () => {
    if (!startsAt || !endsAt) return;
    setSaving(true);
    try {
      await capacityService.saveWorkshopSchedule(workspaceSlug, projectId, issueId, {
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        preparation_minutes: preparationMinutes,
        travel_before_minutes: travelBeforeMinutes,
        travel_after_minutes: travelAfterMinutes,
      });
      await mutate();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workshop scheduled",
        message: "Trainer capacity has been updated.",
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Workshop not scheduled",
        message: "Check the time range and make sure every assignee is an active trainer.",
      });
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await capacityService.deleteWorkshopSchedule(workspaceSlug, projectId, issueId);
      await mutate(null, { revalidate: false });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workshop schedule removed",
        message: "Trainer capacity has been updated.",
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Workshop schedule not removed",
        message: "Try again. The existing schedule is still active.",
      });
    } finally {
      setSaving(false);
    }
  };

  const minuteField = (label: string, value: number, setValue: (value: number) => void) => (
    <label className="grid grid-cols-[1fr_70px] items-center gap-2 text-11 text-secondary">
      {label}
      <input
        type="number"
        min={0}
        max={1440}
        value={value}
        disabled={!isEditable}
        onChange={(event) => setValue(Number(event.target.value))}
        className="min-w-0 rounded border border-subtle bg-surface-2 px-2 py-1 text-right"
      />
    </label>
  );

  return (
    <SidebarPropertyListItem icon={CalendarClock} label="Workshop schedule">
      <div className="space-y-2 rounded-md border border-subtle bg-surface-2 p-2">
        <p className="text-11 text-placeholder">Times shown in {viewerTimezone}</p>
        <p className="text-11 text-placeholder">Every assignee must have an active trainer profile.</p>
        <label className="block text-11 text-secondary">
          Starts
          <input
            type="datetime-local"
            value={startsAt}
            disabled={!isEditable}
            onChange={(event) => setStartsAt(event.target.value)}
            className="mt-1 w-full rounded border border-subtle bg-surface-1 px-2 py-1"
          />
        </label>
        <label className="block text-11 text-secondary">
          Ends
          <input
            type="datetime-local"
            value={endsAt}
            disabled={!isEditable}
            onChange={(event) => setEndsAt(event.target.value)}
            className="mt-1 w-full rounded border border-subtle bg-surface-1 px-2 py-1"
          />
        </label>
        {minuteField("Preparation", preparationMinutes, setPreparationMinutes)}
        {minuteField("Travel before", travelBeforeMinutes, setTravelBeforeMinutes)}
        {minuteField("Travel after", travelAfterMinutes, setTravelAfterMinutes)}
        {isEditable ? (
          <div className="flex gap-2">
            <Button variant="primary" size="sm" loading={saving} disabled={!startsAt || !endsAt} onClick={save}>
              Save schedule
            </Button>
            {data ? (
              <Button variant="secondary" size="sm" disabled={saving} onClick={remove}>
                Remove
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </SidebarPropertyListItem>
  );
}
