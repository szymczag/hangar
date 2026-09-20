/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { TZDate } from "@date-fns/tz";
import type { TTrainerProfile } from "@/services/capacity.service";

export const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function errorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error !== "object" || error === null) return fallback;
  if ("error" in error && typeof error.error === "string") return error.error;
  if ("detail" in error && typeof error.detail === "string") return error.detail;
  return fallback;
}

export function startOfWeek(value: Date, timeZone?: string) {
  const result = new TZDate(value.getTime(), timeZone ?? (value instanceof TZDate ? value.timeZone : undefined));
  const day = result.getDay() || 7;
  result.setDate(result.getDate() - day + 1);
  result.setHours(0, 0, 0, 0);
  return result;
}

export function shiftWeek(value: Date, weeks: number) {
  const result = new TZDate(value.getTime(), value instanceof TZDate ? value.timeZone : undefined);
  result.setDate(result.getDate() + weeks * 7);
  return result;
}

/**
 * The `?week=` parameter, as a local calendar date.
 *
 * Deliberately not `toISOString()`. `startOfWeek` returns local midnight on a
 * Monday; converting that to UTC moves it to the Sunday for every timezone east
 * of Greenwich, so the URL would name the wrong day and reading it back would
 * walk the week backwards one reload at a time.
 */
export function formatWeekParam(value: Date) {
  const month = `${value.getMonth() + 1}`.padStart(2, "0");
  const day = `${value.getDate()}`.padStart(2, "0");
  return `${value.getFullYear()}-${month}-${day}`;
}

/**
 * Read a `?week=` value, falling back to the week containing `fallback`.
 *
 * Anything unparseable gives the fallback rather than an `Invalid Date`, which
 * would otherwise reach the SWR key and the request as `NaN`. The result is
 * snapped to the start of its week, so a URL naming any day inside a week
 * composes the same cache key as one naming the Monday -- without that, two
 * links to the same week would each pay for their own request.
 */
export function parseWeekParam(value: string | null | undefined, fallback: Date, timeZone?: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? "");
  if (!match) return startOfWeek(fallback, timeZone);
  const [, year, month, day] = match;
  // `TZDate` only reads a trailing argument as a zone when it is a string. Handing it
  // `undefined` leaves it as a positional date component -- the hours here -- and the result
  // is an Invalid Date, which the guard below then quietly turns into the fallback week. An
  // omitted zone has to mean local time, so build a plain `Date` for that case.
  const parsed = timeZone
    ? new TZDate(Number(year), Number(month) - 1, Number(day), timeZone)
    : new Date(Number(year), Number(month) - 1, Number(day));
  if (Number.isNaN(parsed.getTime())) return startOfWeek(fallback, timeZone);
  // `new Date(2026, 12, 40)` rolls over silently; reject what did not round-trip.
  if (parsed.getMonth() !== Number(month) - 1 || parsed.getDate() !== Number(day))
    return startOfWeek(fallback, timeZone);
  return startOfWeek(parsed);
}

export function startOfMonth(value: Date, timeZone?: string) {
  const result = new TZDate(value.getTime(), timeZone ?? (value instanceof TZDate ? value.timeZone : undefined));
  result.setDate(1);
  result.setHours(0, 0, 0, 0);
  return result;
}

export function shiftMonth(value: Date, months: number) {
  const result = startOfMonth(value);
  // Set the day first. Stepping from the 31st into a month that has no 31st
  // rolls over into the following one, so January would step to March; starting
  // from the first of the month makes the arithmetic say what it means.
  result.setMonth(result.getMonth() + months);
  return result;
}

/** The `?month=` parameter, as a local calendar month. */
export function formatMonthParam(value: Date) {
  return `${value.getFullYear()}-${`${value.getMonth() + 1}`.padStart(2, "0")}`;
}

/**
 * Read a `?month=` value, falling back to the month containing `fallback`.
 *
 * Same shape as `parseWeekParam` and for the same reasons: a plain `Date` when
 * no zone is given, because `TZDate` reads a trailing `undefined` as a
 * positional component rather than as "local"; and a rejection of anything that
 * did not round-trip, because `new Date(2026, 13, 1)` rolls over in silence.
 */
export function parseMonthParam(value: string | null | undefined, fallback: Date, timeZone?: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(value ?? "");
  if (!match) return startOfMonth(fallback, timeZone);
  const [, year, month] = match;
  const index = Number(month) - 1;
  if (index < 0 || index > 11) return startOfMonth(fallback, timeZone);
  const parsed = timeZone ? new TZDate(Number(year), index, 1, timeZone) : new Date(Number(year), index, 1);
  if (Number.isNaN(parsed.getTime()) || parsed.getMonth() !== index) return startOfMonth(fallback, timeZone);
  return startOfMonth(parsed);
}

export function formatMinutes(value: number) {
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
}

/** Hours to one decimal, for a report where minutes are noise. */
export function formatHours(minutes: number) {
  return `${Math.round((minutes / 60) * 10) / 10}h`;
}

export function connectionCopy(status: string) {
  if (status === "connected") return "Google connected";
  if (status === "not_connected") return "Calendar not connected";
  if (status === "no_calendars_selected") return "Choose calendars";
  return "Availability unknown";
}

export function availabilityCopy(status: string) {
  if (status === "fresh") return "Live availability";
  if (status === "stale") return "Last known availability";
  if (status === "reauthentication_required") return "Reconnect Google";
  if (status === "rate_limited") return "Google rate limited";
  if (status === "provider_unavailable") return "Google unavailable";
  return connectionCopy(status);
}

export function bookingHoursSummary(profile: TTrainerProfile) {
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
