/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

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

export function startOfWeek(value: Date) {
  const result = new Date(value);
  const day = result.getDay() || 7;
  result.setDate(result.getDate() - day + 1);
  result.setHours(0, 0, 0, 0);
  return result;
}

export function shiftWeek(value: Date, weeks: number) {
  const result = new Date(value);
  result.setDate(result.getDate() + weeks * 7);
  return result;
}

export function formatMinutes(value: number) {
  const hours = Math.floor(value / 60);
  const minutes = value % 60;
  return minutes ? `${hours}h ${minutes}m` : `${hours}h`;
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
