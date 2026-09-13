// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { DAY_KEYS } from "./capacity-format.utils";

export type EditableInterval = { id: string; start: string; end: string };
export type EditableWeek = Record<string, EditableInterval[]>;
export type WeeklyHours = Record<string, { start: string; end: string }[]>;

export function editableInterval(start = "09:00", end = "22:00"): EditableInterval {
  return { id: crypto.randomUUID(), start, end };
}

export function editWeek(week: WeeklyHours): EditableWeek {
  return Object.fromEntries(
    DAY_KEYS.map((day) => [day, (week[day] ?? []).map(({ start, end }) => editableInterval(start, end))])
  );
}

export function normalizeBookingTime(value: string): string | null {
  const match = /^(\d{1,2})(?::(\d{2}))?$/.exec(value.trim());
  if (!match || Number(match[1]) > 23 || Number(match[2] ?? 0) > 59) return null;
  return `${match[1].padStart(2, "0")}:${match[2] ?? "00"}`;
}

export function validateBookingWeek(week: EditableWeek) {
  const errors: Record<string, string> = {};
  const schedule: WeeklyHours = {};
  for (const day of DAY_KEYS) {
    const intervals = week[day] ?? [];
    if (intervals.length > 8) errors[day] = "Use at most eight intervals per day.";
    const normalized = intervals
      .map((interval) => {
        const start = normalizeBookingTime(interval.start);
        const end = normalizeBookingTime(interval.end);
        if (!start) errors[`${interval.id}:start`] = "Enter a time from 00:00 to 23:59.";
        if (!end) errors[`${interval.id}:end`] = "Enter a time from 00:00 to 23:59.";
        if (start && end && start >= end) errors[`${interval.id}:end`] = "End must be later than start.";
        return { start: start ?? "", end: end ?? "", id: interval.id };
      })
      .toSorted((a, b) => a.start.localeCompare(b.start));
    for (let i = 1; i < normalized.length; i++) {
      if (normalized[i].start && normalized[i].start < normalized[i - 1].end)
        errors[`${normalized[i].id}:start`] = "Intervals must not overlap.";
    }
    schedule[day] = normalized.map(({ start, end }) => ({ start, end }));
  }
  return { schedule, errors, valid: Object.keys(errors).length === 0 };
}

export function copyBookingDay(week: EditableWeek, source: string, allDays: boolean): EditableWeek {
  return Object.fromEntries(
    DAY_KEYS.map((day) => [
      day,
      day !== source && (allDays || week[day]?.length)
        ? week[source].map(({ start, end }) => editableInterval(start, end))
        : week[day],
    ])
  );
}
