/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { Button } from "@makeplane/propel/components/button";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { CheckboxField } from "@makeplane/propel/components/checkbox-field";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { SelectField } from "@makeplane/propel/components/select-field";
import { TextButton } from "@makeplane/propel/components/text-button";
import { DeleteOutline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
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

const COPY_SOURCE_OPTIONS = DAY_KEYS.map((day, index) => ({ value: day, label: DAY_LABELS[index] }));

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
      });
      setToast({
        type: "success",
        title: "Booking hours saved",
        message: "Capacity now uses this weekly schedule.",
      });
      onSaved();
    } catch (error: unknown) {
      setToast({
        type: "error",
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
        <Button variant="primary" size="md" stretch="auto" loading={saving} onClick={save} label="Save hours" />
      </div>
      <fieldset disabled={saving} className="min-w-0">
        <p className="mb-4 text-body-xs-regular text-secondary">
          Times in {profile.timezone} · From{" "}
          {profile.timezone_source === "google_calendar" ? "your primary Google calendar" : "your Hangar profile"}.
        </p>
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-md bg-surface-2 p-3">
          <SelectField<string>
            label="Copy hours from"
            size="md"
            width="fit"
            options={COPY_SOURCE_OPTIONS}
            value={copySource}
            disabled={saving}
            onValueChange={(day) => {
              if (day) setCopySource(day);
            }}
          />
          <CheckboxField
            label="Include days off"
            size="md"
            checked={copyAll}
            disabled={saving}
            onCheckedChange={(checked) => setCopyAll(checked)}
          />
          <Button
            variant="secondary"
            size="md"
            stretch="auto"
            label={copyAll ? "Set the same for all days" : "Copy to active days"}
            disabled={
              saving ||
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
          />
          <p role="status" className="w-full text-body-xs-regular text-secondary">
            {copyNotice}
          </p>
        </div>
        <div className="divide-y divide-subtle">
          {DAY_KEYS.map((day, index) => (
            <div key={day} className="grid gap-3 py-3 sm:grid-cols-[7rem_1fr]">
              <div className="flex h-9 items-center">
                <Checkbox
                  label={DAY_LABELS[index]}
                  checked={schedule[day].length > 0}
                  disabled={saving}
                  onCheckedChange={() =>
                    setSchedule((current) => ({
                      ...current,
                      [day]: current[day].length ? [] : [editableInterval()],
                    }))
                  }
                />
              </div>
              <div className="min-w-0 space-y-2">
                {schedule[day].map((interval, intervalIndex) => (
                  <div key={interval.id} className="flex items-start gap-2">
                    {(["start", "end"] as const).map((field) => {
                      const key = `${interval.id}:${field}`;
                      const error = submitted || touched[key] ? validation.errors[key] : undefined;
                      return (
                        <label key={field} className="block w-28 text-body-xs-regular text-secondary">
                          {field === "start" ? "From" : "Until"}
                          <span className="mt-1 block">
                            <InputGroup size="lg">
                              <Input
                                size="lg"
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
                              />
                            </InputGroup>
                          </span>
                          {error && (
                            <span id={key} className="mt-1 block text-danger-primary">
                              {error}
                            </span>
                          )}
                        </label>
                      );
                    })}
                    <span className="mt-6">
                      <IconButton
                        variant="ghost"
                        size="lg"
                        icon={<Icon icon={DeleteOutline} />}
                        aria-label={`Remove ${DAY_LABELS[index]} interval ${intervalIndex + 1}`}
                        disabled={saving}
                        onClick={() =>
                          setSchedule((current) => ({
                            ...current,
                            [day]: current[day].filter((value) => value.id !== interval.id),
                          }))
                        }
                      />
                    </span>
                  </div>
                ))}
                {schedule[day].length ? (
                  <TextButton
                    variant="primary"
                    size="md"
                    label="Add interval"
                    disabled={saving || schedule[day].length >= 8}
                    onClick={() =>
                      setSchedule((current) => ({
                        ...current,
                        [day]: [...current[day], editableInterval("13:00", "17:00")],
                      }))
                    }
                  />
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
