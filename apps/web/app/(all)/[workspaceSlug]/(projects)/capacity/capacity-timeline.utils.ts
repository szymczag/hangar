/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TCapacityInterval } from "@/services/capacity.service";

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

export const CAPACITY_INTERVAL_LAYERS: TCapacityInterval["kind"][] = ["working", "google_busy", "workshop"];
