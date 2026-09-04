/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TCapacityInterval } from "@/services/capacity.service";

export type TTimelineRange = { start: string; end: string };

export function dayBounds(weekStart: Date, dayIndex: number) {
  const start = new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + dayIndex, 0, 0, 0, 0);
  const end = new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate() + dayIndex + 1, 0, 0, 0, 0);
  return { start, end };
}

export function intervalPosition(interval: { start: string; end: string }, dayStart: Date, dayEnd: Date) {
  const start = Math.max(new Date(interval.start).getTime(), dayStart.getTime());
  const end = Math.min(new Date(interval.end).getTime(), dayEnd.getTime());
  if (start >= end) return null;
  const duration = dayEnd.getTime() - dayStart.getTime();
  return {
    left: `${((start - dayStart.getTime()) / duration) * 100}%`,
    width: `${((end - start) / duration) * 100}%`,
  };
}

export function intervalLabel(interval: TCapacityInterval) {
  if (interval.kind === "working") return "Working hours";
  if (interval.kind === "google_busy") return "Busy — Google Calendar";
  return interval.work_item?.name ? `Workshop: ${interval.work_item.name}` : "Workshop (details restricted)";
}

function mergeRanges(ranges: TTimelineRange[]) {
  const sorted = ranges
    .map((range) => ({ start: new Date(range.start).getTime(), end: new Date(range.end).getTime() }))
    .filter((range) => range.start < range.end)
    .toSorted((left, right) => left.start - right.start);
  const merged: Array<{ start: number; end: number }> = [];
  for (const range of sorted) {
    const previous = merged.at(-1);
    if (previous && range.start <= previous.end) previous.end = Math.max(previous.end, range.end);
    else merged.push({ ...range });
  }
  return merged;
}

export function availableRanges(intervals: TCapacityInterval[], dayStart: Date, dayEnd: Date): TTimelineRange[] {
  const clip = (interval: TTimelineRange) => ({
    start: Math.max(new Date(interval.start).getTime(), dayStart.getTime()),
    end: Math.min(new Date(interval.end).getTime(), dayEnd.getTime()),
  });
  const working = mergeRanges(
    intervals
      .filter((interval) => interval.kind === "working")
      .map(clip)
      .filter((interval) => interval.start < interval.end)
      .map((interval) => ({ start: new Date(interval.start).toISOString(), end: new Date(interval.end).toISOString() }))
  );
  const blockers = mergeRanges(
    intervals
      .filter((interval) => interval.kind !== "working")
      .map(clip)
      .filter((interval) => interval.start < interval.end)
      .map((interval) => ({ start: new Date(interval.start).toISOString(), end: new Date(interval.end).toISOString() }))
  );
  const result: Array<{ start: number; end: number }> = [];
  for (const window of working) {
    let cursor = window.start;
    for (const blocker of blockers) {
      if (blocker.end <= cursor || blocker.start >= window.end) continue;
      if (cursor < blocker.start) result.push({ start: cursor, end: Math.min(blocker.start, window.end) });
      cursor = Math.max(cursor, blocker.end);
      if (cursor >= window.end) break;
    }
    if (cursor < window.end) result.push({ start: cursor, end: window.end });
  }
  return result.map((range) => ({
    start: new Date(range.start).toISOString(),
    end: new Date(range.end).toISOString(),
  }));
}

export function clippedRanges(intervals: TTimelineRange[], dayStart: Date, dayEnd: Date): TTimelineRange[] {
  return intervals.flatMap((interval) => {
    const start = Math.max(new Date(interval.start).getTime(), dayStart.getTime());
    const end = Math.min(new Date(interval.end).getTime(), dayEnd.getTime());
    return start < end ? [{ start: new Date(start).toISOString(), end: new Date(end).toISOString() }] : [];
  });
}

export function rangeMinutes(ranges: TTimelineRange[]) {
  return Math.round(
    ranges.reduce((total, range) => total + new Date(range.end).getTime() - new Date(range.start).getTime(), 0) / 60_000
  );
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function formatRange(range: TTimelineRange) {
  return `${formatTime(range.start)}–${formatTime(range.end)}`;
}

export const CAPACITY_INTERVAL_LAYERS: TCapacityInterval["kind"][] = ["working", "google_busy", "workshop"];
