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
import {
  copyBookingDay,
  editableInterval,
  editWeek,
  normalizeBookingTime,
  validateBookingWeek,
} from "./schedule-editor.utils";

const capacityService = new CapacityService();

export function ScheduleEditor({
  profile,
  workspaceSlug,
  onSaved,
}: {
  profile: TTrainerProfile;
  workspaceSlug: string;
  onSaved: () => void;
}) {
  const [schedule, setSchedule] = useState(() => editWeek(profile.weekly_schedule));
  const [trainerTimezone, setTrainerTimezone] = useState(profile.timezone);
  const [saving, setSaving] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [submitted, setSubmitted] = useState(false);
  const [copySource, setCopySource] = useState<string>("mon");
  const [copyAll, setCopyAll] = useState(false);
  const [copyNotice, setCopyNotice] = useState("");
  const validation = validateBookingWeek(schedule);

  const setTime = (day: string, id: string, field: "start" | "end", value: string) =>
    setSchedule((current) => ({
      ...current,
      [day]: current[day].map((interval) => (interval.id === id ? { ...interval, [field]: value } : interval)),
    }));

  const save = async () => {
    setSubmitted(true);
    if (!validation.valid || saving) return;
    setSaving(true);
    try {
      await capacityService.updateSchedule(workspaceSlug, profile.user_id, profile.schedule_revision, {
        weekly_schedule: validation.schedule,
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
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-body-sm-medium">Booking hours · {profile.display_name}</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">
            Set the hours when this trainer can be booked. Changes apply after saving.
          </p>
        </div>
        <Button variant="primary" size="sm" loading={saving} onClick={save}>
          Save hours
        </Button>
      </div>
      <fieldset disabled={saving} className="min-w-0">
        <label className="mb-4 block max-w-sm text-body-xs-medium">
          Trainer timezone
          <input
            aria-label="Trainer timezone"
            value={trainerTimezone}
            onChange={(event) => setTrainerTimezone(event.target.value)}
            className="mt-1 w-full rounded border border-subtle bg-surface-2 px-2 py-1.5 text-body-xs-regular"
          />
        </label>
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-md bg-surface-2 p-3">
          <label className="text-body-xs-medium">
            Copy hours from
            <select
              aria-label="Copy hours from"
              value={copySource}
              onChange={(event) => setCopySource(event.target.value)}
              className="ml-2 rounded border border-subtle bg-surface-1 p-2"
            >
              {DAY_KEYS.map((day, index) => (
                <option key={day} value={day}>
                  {DAY_LABELS[index]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-body-xs-regular">
            <input type="checkbox" checked={copyAll} onChange={(event) => setCopyAll(event.target.checked)} />
            Include days off
          </label>
          <Button
            variant="secondary"
            size="sm"
            disabled={
              !schedule[copySource]?.length ||
              !validateBookingWeek({ ...editWeek({}), [copySource]: schedule[copySource] }).valid
            }
            onClick={() => {
              setSchedule((current) => copyBookingDay(current, copySource, copyAll));
              setCopyNotice(
                copyAll
                  ? "Hours copied to all seven days. Save hours to apply."
                  : "Hours copied to the other active days. Save hours to apply."
              );
            }}
          >
            {copyAll ? "Set the same for all days" : "Copy to active days"}
          </Button>
          <p role="status" className="w-full text-body-xs-regular text-secondary">
            {copyNotice}
          </p>
        </div>
        <div className="divide-y divide-subtle">
          {DAY_KEYS.map((day, index) => (
            <div key={day} className="grid gap-3 py-3 sm:grid-cols-[7rem_1fr]">
              <label className="flex h-9 items-center gap-2 text-body-xs-medium">
                <input
                  type="checkbox"
                  checked={schedule[day].length > 0}
                  onChange={() =>
                    setSchedule((current) => ({
                      ...current,
                      [day]: current[day].length ? [] : [editableInterval()],
                    }))
                  }
                />
                {DAY_LABELS[index]}
              </label>
              <div className="min-w-0 space-y-2">
                {schedule[day].map((interval, intervalIndex) => (
                  <div key={interval.id} className="flex items-start gap-2">
                    {(["start", "end"] as const).map((field) => {
                      const key = `${interval.id}:${field}`;
                      const error = submitted || touched[key] ? validation.errors[key] : undefined;
                      return (
                        <label key={field} className="block w-28 text-body-xs-regular text-secondary">
                          {field === "start" ? "From" : "Until"}
                          <input
                            aria-label={`${DAY_LABELS[index]} interval ${intervalIndex + 1} ${field}`}
                            type="text"
                            inputMode="numeric"
                            placeholder="HH:mm"
                            autoComplete="off"
                            value={interval[field]}
                            aria-invalid={Boolean(error)}
                            aria-describedby={error ? key : undefined}
                            onChange={(event) => setTime(day, interval.id, field, event.target.value)}
                            onBlur={() => {
                              setTouched((current) => ({ ...current, [key]: true }));
                              const value = normalizeBookingTime(interval[field]);
                              if (value) setTime(day, interval.id, field, value);
                            }}
                            className="mt-1 h-9 w-full rounded border border-subtle bg-surface-2 px-3 text-body-sm-regular text-primary tabular-nums"
                          />
                          {error && (
                            <span id={key} className="mt-1 block text-danger-primary">
                              {error}
                            </span>
                          )}
                        </label>
                      );
                    })}
                    <button
                      type="button"
                      aria-label={`Remove ${DAY_LABELS[index]} interval ${intervalIndex + 1}`}
                      onClick={() =>
                        setSchedule((current) => ({
                          ...current,
                          [day]: current[day].filter((value) => value.id !== interval.id),
                        }))
                      }
                      className="mt-6 rounded p-2 text-secondary hover:text-danger-primary"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                ))}
                {schedule[day].length ? (
                  <button
                    type="button"
                    disabled={schedule[day].length >= 8}
                    onClick={() =>
                      setSchedule((current) => ({
                        ...current,
                        [day]: [...current[day], editableInterval("13:00", "17:00")],
                      }))
                    }
                    className="text-body-xs-medium text-accent-primary disabled:opacity-50"
                  >
                    Add interval
                  </button>
                ) : (
                  <p className="py-2 text-body-xs-regular text-placeholder">Day off</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </fieldset>
    </section>
  );
}
