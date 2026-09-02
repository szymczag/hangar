/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight, CircleAlert, Link2, Plus, Trash2, Unplug } from "lucide-react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Spinner } from "@plane/ui";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useUserPermissions } from "@/hooks/store/user";
import { useInstance } from "@/hooks/store/use-instance";
import {
  CapacityService,
  type TGoogleCalendar,
  type TTrainerException,
  type TTrainerProfile,
} from "@/services/capacity.service";
import type { Route } from "./+types/page";

const capacityService = new CapacityService();
const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function errorMessage(error: unknown, fallback: string) {
  return typeof error === "object" && error !== null && "error" in error && typeof error.error === "string"
    ? error.error
    : fallback;
}

function startOfWeek(value: Date) {
  const result = new Date(value);
  const day = result.getDay() || 7;
  result.setDate(result.getDate() - day + 1);
  result.setHours(0, 0, 0, 0);
  return result;
}

function ExceptionsEditor({
  profile,
  workspaceSlug,
  onSaved,
}: {
  profile: TTrainerProfile;
  workspaceSlug: string;
  onSaved: () => void;
}) {
  const [exceptions, setExceptions] = useState<TTrainerException[]>(profile.exceptions);
  const [saving, setSaving] = useState(false);
  const setExceptionInterval = (exceptionIndex: number, intervalIndex: number, field: "start" | "end", value: string) =>
    setExceptions((current) =>
      current.map((entry, position) => {
        if (position !== exceptionIndex) return entry;
        const intervals = [...entry.intervals];
        intervals[intervalIndex] = { ...intervals[intervalIndex], [field]: value };
        return { ...entry, intervals };
      })
    );
  const addDate = () => {
    const date = new Date().toISOString().slice(0, 10);
    if (!exceptions.some((item) => item.date === date))
      setExceptions((current) => [...current, { date, mode: "unavailable", intervals: [] }]);
  };
  const save = async () => {
    setSaving(true);
    try {
      await capacityService.updateSchedule(workspaceSlug, profile.user_id, profile.schedule_revision, { exceptions });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Exceptions saved",
        message: "The capacity ledger now reflects these dates.",
      });
      onSaved();
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Exceptions not saved",
        message: errorMessage(error, "Check the dates and try again."),
      });
    } finally {
      setSaving(false);
    }
  };
  return (
    <section className="rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-body-sm-medium">Schedule exceptions</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">
            Mark a date unavailable, or override it with specific working intervals.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={addDate}>
            <Plus className="mr-1 size-3.5" />
            Add date
          </Button>
          <Button variant="primary" size="sm" loading={saving} onClick={save}>
            Save dates
          </Button>
        </div>
      </div>
      {exceptions.length ? (
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {exceptions.map((item, index) => (
            <div key={item.date} className="rounded-md border border-subtle p-2">
              <div className="flex items-center gap-2">
                <input
                  type="date"
                  value={item.date}
                  onChange={(event) =>
                    setExceptions((current) =>
                      current.map((entry, position) =>
                        position === index ? { ...entry, date: event.target.value } : entry
                      )
                    )
                  }
                  className="min-w-0 flex-1 rounded border border-subtle bg-surface-2 px-2 py-1 text-body-xs-regular"
                />
                <select
                  aria-label={`Availability mode for ${item.date}`}
                  value={item.mode}
                  onChange={(event) =>
                    setExceptions((current) =>
                      current.map((entry, position) =>
                        position === index
                          ? {
                              ...entry,
                              mode: event.target.value as TTrainerException["mode"],
                              intervals:
                                event.target.value === "override" && entry.intervals.length === 0
                                  ? [{ start: "09:00", end: "17:00" }]
                                  : entry.intervals,
                            }
                          : entry
                      )
                    )
                  }
                  className="rounded border border-subtle bg-surface-2 px-2 py-1 text-body-xs-regular"
                >
                  <option value="unavailable">Unavailable</option>
                  <option value="override">Custom hours</option>
                </select>
                <button
                  type="button"
                  aria-label={`Remove exception for ${item.date}`}
                  className="rounded p-1 text-secondary hover:text-danger-primary"
                  onClick={() => setExceptions((current) => current.filter((_, position) => position !== index))}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              {item.mode === "override" ? (
                <div className="mt-2 flex flex-col gap-1">
                  {item.intervals.map((interval, intervalIndex) => (
                    <div key={`${interval.start}-${interval.end}`} className="flex items-center gap-1">
                      <input
                        aria-label={`Override interval ${intervalIndex + 1} start`}
                        type="time"
                        value={interval.start}
                        onChange={(event) => setExceptionInterval(index, intervalIndex, "start", event.target.value)}
                        className="rounded border border-subtle bg-surface-2 px-1 py-1 text-11"
                      />
                      <span className="text-11 text-secondary">–</span>
                      <input
                        aria-label={`Override interval ${intervalIndex + 1} end`}
                        type="time"
                        value={interval.end}
                        onChange={(event) => setExceptionInterval(index, intervalIndex, "end", event.target.value)}
                        className="rounded border border-subtle bg-surface-2 px-1 py-1 text-11"
                      />
                      <button
                        type="button"
                        aria-label={`Remove override interval ${intervalIndex + 1}`}
                        onClick={() =>
                          setExceptions((current) =>
                            current.map((entry, position) =>
                              position === index
                                ? {
                                    ...entry,
                                    intervals: entry.intervals.filter((_, itemIndex) => itemIndex !== intervalIndex),
                                  }
                                : entry
                            )
                          )
                        }
                        className="rounded p-1 text-secondary hover:text-danger-primary"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="self-start text-11 text-accent-primary"
                    onClick={() =>
                      setExceptions((current) =>
                        current.map((entry, position) =>
                          position === index
                            ? { ...entry, intervals: [...entry.intervals, { start: "13:00", end: "17:00" }] }
                            : entry
                        )
                      )
                    }
                  >
                    + Add interval
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-body-xs-regular text-placeholder">No dates blocked.</p>
      )}
    </section>
  );
}

function formatMinutes(value: number) {
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

function connectionCopy(status: string) {
  if (status === "connected") return "Google connected";
  if (status === "not_connected") return "Calendar not connected";
  if (status === "no_calendars_selected") return "Choose calendars";
  return "Availability unknown";
}

function availabilityCopy(status: string) {
  if (status === "fresh") return "Live availability";
  if (status === "stale") return "Last known availability";
  if (status === "reauthentication_required") return "Reconnect Google";
  if (status === "rate_limited") return "Google rate limited";
  if (status === "provider_unavailable") return "Google unavailable";
  return connectionCopy(status);
}

function ScheduleEditor({
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
      [day]: current[day]?.length ? [] : [{ start: "09:00", end: "17:00" }],
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
        title: "Working hours saved",
        message: "Capacity now uses this weekly schedule.",
      });
      onSaved();
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Working hours not saved",
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
          <h2 className="text-body-sm-medium">Working week · {profile.display_name}</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">Busy time is subtracted only inside these hours.</p>
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

function CalendarPicker({
  workspaceSlug,
  calendars,
  selectionRevision,
  onSaved,
}: {
  workspaceSlug: string;
  calendars: TGoogleCalendar[];
  selectionRevision: number;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(
    () => new Set(calendars.filter((item) => item.selected).map((item) => item.id))
  );
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await capacityService.selectCalendars(workspaceSlug, [...selected], selectionRevision);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Calendars saved",
        message: "Only anonymous busy ranges will be used.",
      });
      onSaved();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Calendars not saved", message: errorMessage(error, "Try again.") });
    } finally {
      setSaving(false);
    }
  };
  return (
    <section className="rounded-lg border border-subtle bg-surface-1 p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-body-sm-medium">Calendars that block your time</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">
            Hangar reads free/busy ranges, never event details.
          </p>
        </div>
        <Button size="sm" variant="primary" loading={saving} disabled={selected.size === 0} onClick={save}>
          Save calendars
        </Button>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {calendars.map((calendar) => (
          <label
            key={calendar.id}
            className="flex cursor-pointer items-center gap-3 rounded-md border border-subtle px-3 py-2 text-body-xs-regular hover:bg-surface-2"
          >
            <input
              type="checkbox"
              checked={selected.has(calendar.id)}
              onChange={() =>
                setSelected((current) => {
                  const next = new Set(current);
                  if (next.has(calendar.id)) next.delete(calendar.id);
                  else next.add(calendar.id);
                  return next;
                })
              }
            />
            <span className="truncate">{calendar.summary}</span>
            {calendar.primary ? <span className="ml-auto text-11 text-placeholder">Primary</span> : null}
          </label>
        ))}
      </div>
    </section>
  );
}

export default function TrainerCapacityPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const { allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const [trainerCursor, setTrainerCursor] = useState<string | undefined>();
  const [cursorHistory, setCursorHistory] = useState<Array<string | undefined>>([]);
  const [editingTrainerId, setEditingTrainerId] = useState<string | null>(null);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const weekEnd = useMemo(() => new Date(weekStart.getTime() + 7 * 24 * 60 * 60 * 1000), [weekStart]);
  const rangeKey = `${weekStart.toISOString()}:${weekEnd.toISOString()}`;
  const {
    data: trainerPage,
    mutate: mutateTrainers,
    isLoading: trainersLoading,
  } = useSWR(["capacity-trainers", workspaceSlug, trainerCursor], () =>
    capacityService.listTrainers(workspaceSlug, trainerCursor)
  );
  const trainers = trainerPage?.results;
  const trainerIds = trainers?.map((trainer) => trainer.user_id) ?? [];
  const {
    data: capacity,
    error: capacityError,
    mutate: mutateCapacity,
    isLoading: capacityLoading,
  } = useSWR(
    trainers ? ["capacity", workspaceSlug, rangeKey, trainerIds.join(",")] : null,
    () => capacityService.getCapacity(workspaceSlug, weekStart.toISOString(), weekEnd.toISOString(), trainerIds),
    { keepPreviousData: true }
  );
  const { data: ownProfile, mutate: mutateOwnProfile } = useSWR(["capacity-trainer-self", workspaceSlug], () =>
    capacityService.getOwnTrainerProfile(workspaceSlug)
  );
  const editingProfile = trainers?.find((trainer) => trainer.user_id === editingTrainerId);
  const hasActiveProfile = ownProfile?.status === "active";
  const isConnected = hasActiveProfile && ownProfile?.connection_status === "connected";
  const { data: calendars, mutate: mutateCalendars } = useSWR(
    isConnected ? ["capacity-calendars", workspaceSlug] : null,
    () => capacityService.listCalendars(workspaceSlug)
  );

  const refresh = () => Promise.all([mutateTrainers(), mutateOwnProfile(), mutateCapacity()]);
  const optIn = async () => {
    await capacityService.optIn(workspaceSlug);
    await refresh();
  };
  const connect = async () => {
    try {
      const { authorization_url } = await capacityService.startGoogle(workspaceSlug);
      window.location.assign(authorization_url);
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Google Calendar not connected",
        message: errorMessage(error, "Try again."),
      });
    }
  };

  if (config && !config.is_google_calendar_capacity_enabled)
    return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <div className="h-full overflow-y-auto bg-surface-2">
      <PageHead title="Trainer capacity" />
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 p-4 md:p-6">
        <section className="overflow-hidden rounded-xl border border-subtle bg-surface-1">
          <div className="flex flex-col justify-between gap-4 border-b border-subtle px-5 py-5 md:flex-row md:items-end">
            <div>
              <div className="mb-2 flex items-center gap-2 text-11 font-semibold tracking-[0.16em] text-placeholder uppercase">
                <CalendarClock className="size-3.5" /> Capacity ledger
              </div>
              <h1 className="text-xl font-semibold text-primary">See the week before it becomes a conflict.</h1>
              <p className="mt-1 max-w-2xl text-body-sm-regular text-secondary">
                Working hours, anonymous Google busy time, and scheduled workshops in one planning rail.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!hasActiveProfile ? (
                <Button variant="primary" size="sm" onClick={optIn}>
                  {ownProfile ? "Reactivate trainer" : "Become a trainer"}
                </Button>
              ) : null}
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setWeekStart((current) => new Date(current.getTime() - 7 * 86400000))}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <div className="min-w-44 text-center text-body-xs-medium">
                {weekStart.toLocaleDateString(undefined, { day: "numeric", month: "short" })} –{" "}
                {new Date(weekEnd.getTime() - 1).toLocaleDateString(undefined, {
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setWeekStart((current) => new Date(current.getTime() + 7 * 86400000))}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
          {capacityLoading || trainersLoading ? (
            <div className="grid min-h-56 place-items-center">
              <Spinner />
            </div>
          ) : capacityError ? (
            <div role="alert" className="flex min-h-56 flex-col items-center justify-center gap-2 px-5 text-center">
              <CircleAlert className="size-6 text-danger-primary" />
              <h2 className="text-body-sm-medium">Capacity could not be loaded</h2>
              <p className="text-body-xs-regular text-secondary">{errorMessage(capacityError, "Try again shortly.")}</p>
              <Button variant="secondary" size="sm" onClick={() => mutateCapacity()}>
                Retry
              </Button>
            </div>
          ) : capacity?.trainers.length ? (
            <div className="divide-y divide-subtle">
              {capacity.trainers.map((trainer) => {
                const availablePercent = trainer.working_minutes
                  ? Math.round((trainer.available_minutes / trainer.working_minutes) * 100)
                  : 0;
                const busyPercent = Math.max(0, 100 - availablePercent);
                return (
                  <article
                    key={trainer.trainer_id}
                    className="grid gap-4 px-5 py-4 lg:grid-cols-[220px_1fr_180px] lg:items-center"
                  >
                    <div>
                      <h2 className="text-body-sm-medium text-primary">{trainer.display_name}</h2>
                      <p className="mt-1 text-11 text-secondary">
                        {availabilityCopy(trainer.availability_status)} · {trainer.timezone}
                      </p>
                    </div>
                    <div>
                      <div className="bg-success-secondary flex h-7 overflow-hidden rounded-md">
                        <div
                          className="bg-danger-secondary transition-[width]"
                          style={{ width: `${busyPercent}%` }}
                          title={`${formatMinutes(trainer.unavailable_minutes)} unavailable`}
                        />
                        <div
                          className="border-success-primary/30 border-l"
                          style={{ width: `${availablePercent}%` }}
                          title={`${formatMinutes(trainer.available_minutes)} available`}
                        />
                      </div>
                      <div className="mt-2 flex gap-4 text-11 text-secondary">
                        <span>Google {formatMinutes(trainer.google_busy_minutes)}</span>
                        <span>Workshops {formatMinutes(trainer.workshop_minutes)}</span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-3 lg:block lg:text-right">
                      <div className="text-lg font-semibold text-primary tabular-nums">
                        {formatMinutes(trainer.available_minutes)}
                      </div>
                      <div className="text-11 text-placeholder">of {formatMinutes(trainer.working_minutes)} free</div>
                      {trainer.conflicts.length ? (
                        <div className="mt-1 inline-flex items-center gap-1 text-11 text-danger-primary">
                          <CircleAlert className="size-3" /> {trainer.conflicts.length} conflict
                          {trainer.conflicts.length === 1 ? "" : "s"}
                        </div>
                      ) : null}
                      {isAdmin ? (
                        <button
                          type="button"
                          className="mt-2 text-11 text-accent-primary"
                          onClick={() => setEditingTrainerId(trainer.trainer_id)}
                        >
                          Manage schedule
                        </button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="flex min-h-56 flex-col items-center justify-center gap-3 px-5 text-center">
              <CalendarClock className="size-8 text-placeholder" />
              <div>
                <h2 className="text-body-sm-medium">No trainers yet</h2>
                <p className="mt-1 text-body-xs-regular text-secondary">
                  Opt in to start the workspace capacity ledger.
                </p>
              </div>
              {!hasActiveProfile ? (
                <Button variant="primary" onClick={optIn}>
                  {ownProfile ? "Reactivate trainer" : "Become a trainer"}
                </Button>
              ) : null}
            </div>
          )}
          {(cursorHistory.length > 0 || trainerPage?.next_cursor) && (
            <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-3">
              <Button
                variant="secondary"
                size="sm"
                disabled={cursorHistory.length === 0}
                onClick={() => {
                  setTrainerCursor(cursorHistory[cursorHistory.length - 1]);
                  setCursorHistory((current) => current.slice(0, -1));
                }}
              >
                Previous trainers
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={!trainerPage?.next_cursor}
                onClick={() => {
                  setCursorHistory((current) => [...current, trainerCursor]);
                  setTrainerCursor(trainerPage?.next_cursor ?? undefined);
                }}
              >
                Next trainers
              </Button>
            </div>
          )}
        </section>

        {isAdmin && editingProfile ? (
          <section aria-label={`Manage ${editingProfile.display_name}`} className="flex flex-col gap-4">
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
              onSaved={refresh}
            />
            <ExceptionsEditor
              key={`${editingProfile.id}-${editingProfile.schedule_revision}-exceptions`}
              profile={editingProfile}
              workspaceSlug={workspaceSlug}
              onSaved={refresh}
            />
          </section>
        ) : null}

        {ownProfile && hasActiveProfile ? (
          <>
            {!isAdmin || editingTrainerId !== ownProfile.user_id ? (
              <>
                <ScheduleEditor
                  key={`${ownProfile.id}-${ownProfile.schedule_revision}-schedule`}
                  profile={ownProfile}
                  workspaceSlug={workspaceSlug}
                  onSaved={refresh}
                />
                <ExceptionsEditor
                  key={`${ownProfile.id}-${ownProfile.schedule_revision}-exceptions`}
                  profile={ownProfile}
                  workspaceSlug={workspaceSlug}
                  onSaved={refresh}
                />
              </>
            ) : null}
            {isConnected && calendars ? (
              <CalendarPicker
                workspaceSlug={workspaceSlug}
                calendars={calendars.calendars}
                selectionRevision={calendars.selection_revision}
                onSaved={() => Promise.all([mutateCalendars(), mutateCapacity()]).then(() => undefined)}
              />
            ) : (
              <section className="flex flex-col justify-between gap-4 rounded-lg border border-subtle bg-surface-1 p-4 md:flex-row md:items-center">
                <div>
                  <h2 className="text-body-sm-medium">Google Calendar</h2>
                  <p className="mt-1 text-body-xs-regular text-secondary">
                    Connect read-only free/busy access. Event names and details never enter Hangar.
                  </p>
                </div>
                <Button variant="primary" onClick={connect}>
                  <Link2 className="mr-2 size-4" />
                  Connect Google Calendar
                </Button>
              </section>
            )}
            {isConnected ? (
              <button
                type="button"
                className="self-end text-11 text-secondary hover:text-danger-primary"
                onClick={async () => {
                  await capacityService.disconnectGoogle(workspaceSlug);
                  await refresh();
                }}
              >
                <Unplug className="mr-1 inline size-3" />
                Disconnect Google Calendar
              </button>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
