/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState, type FC } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CalendarClock, CarFront, CircleAlert, Clock3, Timer } from "lucide-react";
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

const fieldClassName =
  "h-7.5 w-full min-w-0 rounded-sm border border-transparent bg-transparent px-2 text-body-xs-regular hover:border-subtle hover:bg-surface-2 focus:border-accent-primary focus:bg-surface-1";

function MinuteProperty({
  icon,
  label,
  value,
  disabled,
  onChange,
}: {
  icon: FC<{ className?: string }>;
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <SidebarPropertyListItem icon={icon} label={label}>
      <div className="relative w-full">
        <input
          aria-label={`${label} in minutes`}
          type="number"
          min={0}
          max={1440}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(Number(event.target.value))}
          className={`${fieldClassName} pr-10`}
        />
        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-11 text-placeholder">
          min
        </span>
      </div>
    </SidebarPropertyListItem>
  );
}

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
  const { data, error, isLoading, mutate } = useSWR<TWorkshopSchedule | null>(
    isWorkshop ? ["workshop-schedule", workspaceSlug, projectId, issueId] : null,
    () => capacityService.getWorkshopSchedule(workspaceSlug, projectId, issueId)
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

  const blockedFrom = startsAt
    ? new Date(new Date(startsAt).getTime() - (preparationMinutes + travelBeforeMinutes) * 60_000)
    : null;
  const blockedUntil = endsAt ? new Date(new Date(endsAt).getTime() + travelAfterMinutes * 60_000) : null;
  const blockedLabel =
    blockedFrom && blockedUntil
      ? `${blockedFrom.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} – ${blockedUntil.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}`
      : "Set start and end";

  return (
    <>
      <SidebarPropertyListItem icon={CalendarClock} label="Workshop starts">
        <label className="w-full">
          <input
            aria-label={`Workshop starts in ${viewerTimezone}`}
            type="datetime-local"
            value={startsAt}
            disabled={!isEditable}
            onChange={(event) => setStartsAt(event.target.value)}
            className={fieldClassName}
          />
        </label>
      </SidebarPropertyListItem>
      <SidebarPropertyListItem icon={CalendarClock} label="Workshop ends">
        <label className="w-full">
          <input
            aria-label={`Workshop ends in ${viewerTimezone}`}
            type="datetime-local"
            value={endsAt}
            disabled={!isEditable}
            onChange={(event) => setEndsAt(event.target.value)}
            className={fieldClassName}
          />
        </label>
      </SidebarPropertyListItem>
      <MinuteProperty
        icon={Timer}
        label="Preparation"
        value={preparationMinutes}
        disabled={!isEditable}
        onChange={setPreparationMinutes}
      />
      <MinuteProperty
        icon={CarFront}
        label="Travel before"
        value={travelBeforeMinutes}
        disabled={!isEditable}
        onChange={setTravelBeforeMinutes}
      />
      <MinuteProperty
        icon={CarFront}
        label="Travel after"
        value={travelAfterMinutes}
        disabled={!isEditable}
        onChange={setTravelAfterMinutes}
      />
      <SidebarPropertyListItem icon={Clock3} label="Trainer blocked">
        <div className="w-full px-2 py-1 text-body-xs-regular whitespace-normal text-secondary" title={blockedLabel}>
          {blockedLabel}
        </div>
      </SidebarPropertyListItem>
      {error ? (
        <SidebarPropertyListItem icon={CircleAlert} label="Schedule status">
          <p role="alert" className="px-2 py-1 text-body-xs-regular whitespace-normal text-danger-primary">
            Schedule could not be loaded. Try again.
          </p>
        </SidebarPropertyListItem>
      ) : null}
      <SidebarPropertyListItem icon={CalendarClock} label="Schedule actions">
        {isEditable ? (
          <div className="flex w-full flex-wrap gap-2">
            <Button
              variant="primary"
              size="sm"
              loading={saving || isLoading}
              disabled={!startsAt || !endsAt || Boolean(error)}
              onClick={save}
            >
              Save schedule
            </Button>
            {data ? (
              <Button variant="secondary" size="sm" disabled={saving} onClick={remove}>
                Remove
              </Button>
            ) : null}
          </div>
        ) : (
          <span className="px-2 text-11 text-placeholder">Times shown in {viewerTimezone}</span>
        )}
      </SidebarPropertyListItem>
    </>
  );
}
