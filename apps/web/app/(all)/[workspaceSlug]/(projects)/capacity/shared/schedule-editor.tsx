/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CapacityService, type TTrainerProfile } from "@/services/capacity.service";
import { DAY_KEYS, DAY_LABELS, errorMessage } from "./capacity-format.utils";

const capacityService = new CapacityService();

/**
 * A trainer's weekly booking hours and timezone.
 *
 * Presentational on purpose: it does not decide who may edit whom. The server
 * does that -- `_may_edit()` requires the requester to be the trainer or a
 * workspace admin -- so the only job left on the client is deciding where the
 * trigger appears. `/capacity` offers it for yourself, `/capacity/team` offers
 * it to admins for anyone.
 */
export function ScheduleEditor({
  profile,
  workspaceSlug,
  onSaved,
}: {
  profile: TTrainerProfile;
  workspaceSlug: string;
  onSaved: () => void;
}) {
  const [schedule, setSchedule] = useState(profile.weekly_schedule);
  const [trainerTimezone, setTrainerTimezone] = useState(profile.timezone);
  const [saving, setSaving] = useState(false);

  const setTime = (day: string, intervalIndex: number, field: "start" | "end", value: string) => {
    setSchedule((current) => {
      const intervals = [...(current[day] ?? [])];
      intervals[intervalIndex] = { ...intervals[intervalIndex], [field]: value };
      return { ...current, [day]: intervals };
    });
  };

  const addInterval = (day: string) =>
    setSchedule((current) => ({ ...current, [day]: [...(current[day] ?? []), { start: "13:00", end: "17:00" }] }));

  const removeInterval = (day: string, intervalIndex: number) =>
    setSchedule((current) => ({
      ...current,
      [day]: (current[day] ?? []).filter((_, index) => index !== intervalIndex),
    }));

  const toggleDay = (day: string) => {
    setSchedule((current) => ({
      ...current,
      [day]: current[day]?.length ? [] : [{ start: "09:00", end: "22:00" }],
    }));
  };

  const save = async () => {
    setSaving(true);
    try {
      await capacityService.updateSchedule(workspaceSlug, profile.user_id, profile.schedule_revision, {
        weekly_schedule: schedule,
        timezone: trainerTimezone,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Booking hours saved",
        message: "Capacity now uses this weekly schedule.",
      });
      onSaved();
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Booking hours not saved",
        message: errorMessage(error, "Check the time ranges and try again."),
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-body-sm-medium">Booking hours · {profile.display_name}</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">
            Set the weekly windows in which this trainer may be booked. Google busy time and scheduled workshops are
            subtracted inside them.
          </p>
        </div>
        <Button variant="primary" size="sm" loading={saving} onClick={save}>
          Save hours
        </Button>
      </div>
      <label className="mb-4 block max-w-sm text-body-xs-medium">
        Trainer timezone
        <input
          aria-label="Trainer timezone"
          value={trainerTimezone}
          onChange={(event) => setTrainerTimezone(event.target.value)}
          placeholder="Europe/Warsaw"
          className="mt-1 w-full rounded border border-subtle bg-surface-2 px-2 py-1.5 text-body-xs-regular"
        />
      </label>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {DAY_KEYS.map((day, index) => {
          const intervals = schedule[day] ?? [];
          return (
            <div key={day} className="flex min-h-12 items-center gap-2 rounded-md border border-subtle px-3 py-2">
              <label className="flex w-10 cursor-pointer items-center gap-2 self-start pt-1 text-body-xs-medium">
                <input type="checkbox" checked={intervals.length > 0} onChange={() => toggleDay(day)} />
                {DAY_LABELS[index]}
              </label>
              {intervals.length ? (
                <div className="flex min-w-0 flex-1 flex-col gap-1 text-11 text-secondary">
                  {intervals.map((interval, intervalIndex) => (
                    <div key={`${interval.start}-${interval.end}`} className="flex items-center gap-1">
                      <input
                        aria-label={`${DAY_LABELS[index]} interval ${intervalIndex + 1} start`}
                        type="time"
                        value={interval.start}
                        onChange={(event) => setTime(day, intervalIndex, "start", event.target.value)}
                        className="min-w-0 rounded border border-subtle bg-surface-2 px-1 py-1"
                      />
                      <span>–</span>
                      <input
                        aria-label={`${DAY_LABELS[index]} interval ${intervalIndex + 1} end`}
                        type="time"
                        value={interval.end}
                        onChange={(event) => setTime(day, intervalIndex, "end", event.target.value)}
                        className="min-w-0 rounded border border-subtle bg-surface-2 px-1 py-1"
                      />
                      <button
                        type="button"
                        aria-label={`Remove ${DAY_LABELS[index]} interval ${intervalIndex + 1}`}
                        onClick={() => removeInterval(day, intervalIndex)}
                        className="rounded p-1 hover:text-danger-primary"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => addInterval(day)}
                    className="self-start text-11 text-accent-primary"
                  >
                    + Add interval
                  </button>
                </div>
              ) : (
                <span className="text-11 text-placeholder">Off</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
