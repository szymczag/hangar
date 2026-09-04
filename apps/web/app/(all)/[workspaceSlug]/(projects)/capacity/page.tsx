/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight, CircleAlert, Link2, Trash2, Unplug } from "lucide-react";
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
  CapacityRequestError,
  type TGoogleCalendar,
  type TTrainerCapacity,
  type TTrainerProfile,
} from "@/services/capacity.service";
import type { Route } from "./+types/page";
import { CAPACITY_INTERVAL_LAYERS, dayBounds, intervalLabel, intervalPosition } from "./capacity-timeline.utils";

const capacityService = new CapacityService();
const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function errorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error !== "object" || error === null) return fallback;
  if ("error" in error && typeof error.error === "string") return error.error;
  if ("detail" in error && typeof error.detail === "string") return error.detail;
  return fallback;
}

function startOfWeek(value: Date) {
  const result = new Date(value);
  const day = result.getDay() || 7;
  result.setDate(result.getDate() - day + 1);
  result.setHours(0, 0, 0, 0);
  return result;
}

function shiftWeek(value: Date, weeks: number) {
  const result = new Date(value);
  result.setDate(result.getDate() + weeks * 7);
  return result;
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

function TrainerWeekTimeline({ trainer, weekStart }: { trainer: TTrainerCapacity; weekStart: Date }) {
  return (
    <div className="bg-subtle grid min-w-[1120px] grid-cols-7 gap-px overflow-hidden rounded-md border border-subtle">
      {DAY_KEYS.map((day, dayIndex) => {
        const bounds = dayBounds(weekStart, dayIndex);
        return (
          <div
            key={day}
            className="relative h-14 min-w-40 bg-surface-2"
            aria-label={`${DAY_LABELS[dayIndex]} schedule`}
          >
            {[0, 6, 12, 18, 24].map((hour) => (
              <span
                key={hour}
                aria-hidden="true"
                className="absolute top-0 bottom-0 z-0 border-l border-subtle text-[8px] text-placeholder"
                style={{ left: `${(hour / 24) * 100}%` }}
              >
                <span className={hour === 24 ? "-translate-x-full" : ""}>{String(hour).padStart(2, "0")}</span>
              </span>
            ))}
            {CAPACITY_INTERVAL_LAYERS.flatMap((kind) =>
              trainer.intervals
                .filter((interval) => interval.kind === kind)
                .map((interval) => {
                  const position = intervalPosition(interval, bounds.start, bounds.end);
                  if (!position) return null;
                  const className =
                    interval.kind === "working"
                      ? "top-3 bottom-1 z-10 bg-success-secondary"
                      : interval.kind === "google_busy"
                        ? "top-4 bottom-2 z-20 bg-neutral-500/70"
                        : "top-4 bottom-2 z-20 bg-accent-primary/80";
                  const label = intervalLabel(interval);
                  return (
                    <button
                      key={`${interval.kind}-${interval.start}-${interval.end}-${interval.work_item?.id ?? "anonymous"}`}
                      type="button"
                      aria-label={`${label}, ${new Date(interval.start).toLocaleString()} to ${new Date(interval.end).toLocaleString()}`}
                      title={label}
                      className={`absolute rounded-sm ${className}`}
                      style={position}
                    />
                  );
                })
            )}
            {trainer.conflicts.map((conflict) => {
              const position = intervalPosition(conflict, bounds.start, bounds.end);
              if (!position) return null;
              return (
                <span
                  key={`${conflict.kind}-${conflict.start}-${conflict.end}`}
                  role="img"
                  aria-label={`Conflict: ${conflict.kind.replaceAll("_", " ")}`}
                  title={`Conflict: ${conflict.kind.replaceAll("_", " ")}`}
                  className="border-danger-primary absolute top-0 bottom-0 z-30 border"
                  style={{
                    ...position,
                    backgroundImage:
                      "repeating-linear-gradient(135deg, transparent, transparent 3px, rgb(var(--color-danger-primary)) 3px, rgb(var(--color-danger-primary)) 5px)",
                  }}
                />
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function bookingHoursSummary(profile: TTrainerProfile) {
  const grouped = new Map<string, number[]>();
  DAY_KEYS.forEach((day, index) => {
    const intervals = profile.weekly_schedule[day] ?? [];
    if (!intervals.length) return;
    const label = intervals.map((interval) => `${interval.start}–${interval.end}`).join(", ");
    grouped.set(label, [...(grouped.get(label) ?? []), index]);
  });
  const groups = [...grouped.entries()].map(([hours, dayIndexes]) => {
    const consecutive = dayIndexes.every((dayIndex, index) => index === 0 || dayIndex === dayIndexes[index - 1] + 1);
    const days =
      consecutive && dayIndexes.length > 1
        ? `${DAY_LABELS[dayIndexes[0]]}–${DAY_LABELS[dayIndexes.at(-1) ?? 0]}`
        : dayIndexes.map((dayIndex) => DAY_LABELS[dayIndex]).join(", ");
    return `${days} ${hours}`;
  });
  return groups.length ? groups.join(" · ") : "No booking hours";
}

function BookingHoursSummary({ profile, onManage }: { profile: TTrainerProfile; onManage: () => void }) {
  return (
    <section className="flex flex-col justify-between gap-4 rounded-lg border border-subtle bg-surface-1 p-4 md:flex-row md:items-center">
      <div>
        <h2 className="text-body-sm-medium">Booking hours · {profile.display_name}</h2>
        <p className="mt-1 text-body-xs-regular text-secondary">{bookingHoursSummary(profile)}</p>
        <p className="mt-1 text-11 text-placeholder">
          {profile.timezone} · Google busy time and scheduled workshops are subtracted inside these hours.
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={onManage}>
        Manage schedule
      </Button>
    </section>
  );
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
  const [selected, setSelected] = useState(() => {
    const saved = calendars.filter((item) => item.selected).map((item) => item.id);
    const primary = calendars.find((item) => item.primary)?.id;
    return new Set(saved.length || !primary ? saved : [primary]);
  });
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
      {selected.size === 0 ? (
        <p role="alert" className="mt-2 text-11 text-danger-primary">
          Select at least one blocking calendar. Primary may be replaced by another calendar.
        </p>
      ) : null}
    </section>
  );
}

export default function TrainerCapacityPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const { allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const [trainerCursor, setTrainerCursor] = useState<string | undefined>();
  const [cursorHistory, setCursorHistory] = useState<Array<string | undefined>>([]);
  const [editingTrainerId, setEditingTrainerId] = useState<string | null>(null);
  const [optingIn, setOptingIn] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const capacityRefreshRef = useRef<Promise<unknown> | null>(null);
  const weekEnd = useMemo(() => shiftWeek(weekStart, 1), [weekStart]);
  const rangeKey = `${weekStart.toISOString()}:${weekEnd.toISOString()}`;
  const {
    data: trainerPage,
    mutate: mutateTrainers,
    isLoading: trainersLoading,
  } = useSWR(featureEnabled ? ["capacity-trainers", workspaceSlug, trainerCursor] : null, () =>
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
    featureEnabled && trainers ? ["capacity", workspaceSlug, rangeKey, trainerIds.join(",")] : null,
    () => capacityService.getCapacity(workspaceSlug, weekStart.toISOString(), weekEnd.toISOString(), trainerIds),
    {
      keepPreviousData: true,
      dedupingInterval: 5_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      onErrorRetry: (error, _key, _config, revalidate, { retryCount }) => {
        if (retryCount >= 3) return;
        const retryAfter = error instanceof CapacityRequestError ? error.retryAfterSeconds : undefined;
        const delay = Math.min(60, Math.max(retryAfter ?? 0, 5 * 2 ** retryCount));
        globalThis.setTimeout(() => revalidate({ retryCount }), delay * 1000);
      },
    }
  );
  const { data: ownProfile, mutate: mutateOwnProfile } = useSWR(
    featureEnabled ? ["capacity-trainer-self", workspaceSlug] : null,
    () => capacityService.getOwnTrainerProfile(workspaceSlug)
  );
  const editingProfile =
    trainers?.find((trainer) => trainer.user_id === editingTrainerId) ??
    (ownProfile?.user_id === editingTrainerId ? ownProfile : undefined);
  const hasActiveProfile = ownProfile?.status === "active";
  const isConnected = hasActiveProfile && ownProfile?.connection_status === "connected";
  const { data: calendars, mutate: mutateCalendars } = useSWR(
    featureEnabled && isConnected ? ["capacity-calendars", workspaceSlug] : null,
    () => capacityService.listCalendars(workspaceSlug)
  );

  const refreshCapacity = useCallback(() => {
    if (capacityRefreshRef.current) return capacityRefreshRef.current;
    capacityRefreshRef.current = mutateCapacity().finally(() => {
      capacityRefreshRef.current = null;
    });
    return capacityRefreshRef.current;
  }, [mutateCapacity]);
  const refresh = useCallback(async () => {
    await Promise.all([mutateTrainers(), mutateOwnProfile()]);
    await refreshCapacity();
  }, [mutateOwnProfile, mutateTrainers, refreshCapacity]);
  const optIn = async () => {
    setOptingIn(true);
    try {
      await capacityService.optIn(workspaceSlug);
      await refresh();
    } finally {
      setOptingIn(false);
    }
  };
  const connect = async () => {
    setConnecting(true);
    try {
      const { authorization_url } = await capacityService.startGoogle(workspaceSlug);
      window.location.assign(authorization_url);
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Google Calendar not connected",
        message: errorMessage(error, "Try again."),
      });
      setConnecting(false);
    }
  };
  const disconnect = async () => {
    if (!window.confirm("Disconnect Google Calendar and remove its cached availability from Hangar?")) return;
    setDisconnecting(true);
    try {
      await capacityService.disconnectGoogle(workspaceSlug);
      await refresh();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Google Calendar disconnected",
        message: "Cached Google availability was removed.",
      });
    } catch (error: unknown) {
      const mayForce =
        typeof error === "object" &&
        error !== null &&
        "can_force_local_disconnect" in error &&
        error.can_force_local_disconnect === true;
      if (
        mayForce &&
        window.confirm(
          "Google could not revoke the token. Remove the connection from Hangar anyway? You may also need to revoke Hangar in your Google Account."
        )
      ) {
        await capacityService.disconnectGoogle(workspaceSlug, true);
        await refresh();
      } else {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Google Calendar remains connected",
          message: errorMessage(error, "Try again later."),
        });
      }
    } finally {
      setDisconnecting(false);
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
              <h1 className="text-xl font-semibold text-primary">Find a trainer and time.</h1>
              <p className="mt-1 max-w-2xl text-body-sm-regular text-secondary">
                Working hours, anonymous Google busy time, and scheduled workshops in one planning rail.
              </p>
            </div>
            <div className="flex items-center gap-2">
              {!hasActiveProfile ? (
                <Button variant="primary" size="sm" loading={optingIn} onClick={optIn}>
                  {ownProfile ? "Reactivate trainer" : "Become a trainer"}
                </Button>
              ) : null}
              <Button
                variant="secondary"
                size="sm"
                aria-label="Previous week"
                onClick={() => setWeekStart((current) => shiftWeek(current, -1))}
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
                aria-label="Next week"
                onClick={() => setWeekStart((current) => shiftWeek(current, 1))}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
          {(capacityLoading || trainersLoading) && !capacity ? (
            <div className="grid min-h-56 place-items-center">
              <Spinner />
            </div>
          ) : capacityError && !capacity ? (
            <div role="alert" className="flex min-h-56 flex-col items-center justify-center gap-2 px-5 text-center">
              <CircleAlert className="size-6 text-danger-primary" />
              <h2 className="text-body-sm-medium">Capacity could not be loaded</h2>
              <p className="text-body-xs-regular text-secondary">{errorMessage(capacityError, "Try again shortly.")}</p>
              <Button variant="secondary" size="sm" onClick={() => refreshCapacity()}>
                Retry
              </Button>
            </div>
          ) : capacity?.trainers.length ? (
            <div className="overflow-x-auto">
              <div className="min-w-[1510px]">
                {capacityError ? (
                  <div
                    role="status"
                    className="bg-warning-secondary border-b border-subtle px-5 py-2 text-11 text-secondary"
                  >
                    Availability is being refreshed. The last request was rate limited or temporarily unavailable.
                  </div>
                ) : null}
                <div className="grid grid-cols-[190px_1fr_160px] items-end gap-4 border-b border-subtle bg-surface-2 px-5 py-3">
                  <div className="text-11 font-semibold tracking-wide text-placeholder uppercase">Trainer</div>
                  <div className="grid grid-cols-7 gap-px text-center text-11 text-secondary">
                    {DAY_KEYS.map((day, index) => (
                      <div key={day}>
                        <span className="font-medium text-primary">{DAY_LABELS[index]}</span>{" "}
                        {dayBounds(weekStart, index).start.toLocaleDateString(undefined, { day: "numeric" })}
                      </div>
                    ))}
                  </div>
                  <div className="text-right text-11 font-semibold tracking-wide text-placeholder uppercase">Free</div>
                </div>
                <div className="divide-y divide-subtle">
                  {capacity.trainers.map((trainer) => (
                    <article
                      key={trainer.trainer_id}
                      className="grid grid-cols-[190px_1fr_160px] items-center gap-4 px-5 py-4"
                    >
                      <div>
                        <h2 className="text-body-sm-medium text-primary">{trainer.display_name}</h2>
                        <p className="mt-1 text-11 text-secondary">
                          {availabilityCopy(trainer.availability_status)} · {trainer.timezone}
                        </p>
                      </div>
                      <div>
                        <TrainerWeekTimeline trainer={trainer} weekStart={weekStart} />
                        <div className="mt-2 flex gap-4 text-11 text-secondary">
                          <span>Google {formatMinutes(trainer.google_busy_minutes)}</span>
                          <span>Workshops {formatMinutes(trainer.workshop_minutes)}</span>
                        </div>
                      </div>
                      <div className="text-right">
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
                        {isAdmin || trainer.trainer_id === ownProfile?.user_id ? (
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
                  ))}
                </div>
                <div
                  className="flex flex-wrap items-center gap-4 border-t border-subtle bg-surface-2 px-5 py-3 text-11 text-secondary"
                  aria-label="Timeline legend"
                >
                  <span className="inline-flex items-center gap-1.5">
                    <span className="bg-success-secondary ring-success-primary/30 size-2.5 rounded-sm ring-1" />
                    Working hours
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="bg-neutral-500/55 size-2.5 rounded-sm" />
                    Google busy
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2.5 rounded-sm bg-accent-primary/70" />
                    Workshop
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="border-danger-primary bg-danger-secondary size-2.5 rounded-sm border" />
                    Conflict
                  </span>
                  <span className="ml-auto">Times shown in {Intl.DateTimeFormat().resolvedOptions().timeZone}</span>
                </div>
              </div>
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
                <Button variant="primary" loading={optingIn} onClick={optIn}>
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

        {editingProfile && (isAdmin || editingProfile.user_id === ownProfile?.user_id) ? (
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
          </section>
        ) : null}

        {ownProfile && hasActiveProfile ? (
          <>
            {editingTrainerId !== ownProfile.user_id ? (
              <BookingHoursSummary profile={ownProfile} onManage={() => setEditingTrainerId(ownProfile.user_id)} />
            ) : null}
            {isConnected && calendars ? (
              <CalendarPicker
                workspaceSlug={workspaceSlug}
                calendars={calendars.calendars}
                selectionRevision={calendars.selection_revision}
                onSaved={async () => {
                  await mutateCalendars();
                  await refreshCapacity();
                }}
              />
            ) : (
              <section className="flex flex-col justify-between gap-4 rounded-lg border border-subtle bg-surface-1 p-4 md:flex-row md:items-center">
                <div>
                  <h2 className="text-body-sm-medium">Google Calendar</h2>
                  <p className="mt-1 text-body-xs-regular text-secondary">
                    Connect read-only free/busy access. Event names and details never enter Hangar.
                  </p>
                </div>
                <Button variant="primary" loading={connecting} onClick={connect}>
                  <Link2 className="mr-2 size-4" />
                  Connect Google Calendar
                </Button>
              </section>
            )}
            {isConnected ? (
              <button
                type="button"
                className="self-end text-11 text-secondary hover:text-danger-primary"
                disabled={disconnecting}
                onClick={disconnect}
              >
                <Unplug className="mr-1 inline size-3" />
                {disconnecting ? "Disconnecting…" : "Disconnect Google Calendar"}
              </button>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
