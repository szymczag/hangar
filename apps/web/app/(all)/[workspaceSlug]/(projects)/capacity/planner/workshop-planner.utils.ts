/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import type { TTrainerCapacity } from "@/services/capacity.service";
import { availableRanges } from "../shared/capacity-timeline.utils";

export type TWorkshopCandidate = {
  trainerId: string;
  trainerName: string;
  timezone: string;
  availabilityStatus: string;
  workshopStartsAt: string;
  workshopEndsAt: string;
  blockedStartsAt: string;
  blockedEndsAt: string;
};

export function findWorkshopCandidates(
  trainers: TTrainerCapacity[],
  trainerIds: string[],
  windowStart: Date,
  windowEnd: Date,
  durationMinutes: number,
  preparationMinutes: number,
  travelBeforeMinutes: number,
  travelAfterMinutes: number
): TWorkshopCandidate[] {
  const beforeMinutes = preparationMinutes + travelBeforeMinutes;
  const totalMinutes = beforeMinutes + durationMinutes + travelAfterMinutes;
  if (durationMinutes <= 0 || totalMinutes <= 0 || windowStart >= windowEnd) return [];
  const selected = new Set(trainerIds);
  const candidates: TWorkshopCandidate[] = [];

  for (const trainer of trainers) {
    if (!selected.has(trainer.trainer_id)) continue;
    for (const range of availableRanges(trainer.intervals, windowStart, windowEnd)) {
      const blockedStart = new Date(range.start);
      const blockedEnd = new Date(blockedStart.getTime() + totalMinutes * 60_000);
      if (blockedEnd > new Date(range.end)) continue;
      const workshopStart = new Date(blockedStart.getTime() + beforeMinutes * 60_000);
      const workshopEnd = new Date(workshopStart.getTime() + durationMinutes * 60_000);
      candidates.push({
        trainerId: trainer.trainer_id,
        trainerName: trainer.display_name,
        timezone: trainer.timezone,
        availabilityStatus: trainer.availability_status,
        workshopStartsAt: workshopStart.toISOString(),
        workshopEndsAt: workshopEnd.toISOString(),
        blockedStartsAt: blockedStart.toISOString(),
        blockedEndsAt: blockedEnd.toISOString(),
      });
    }
  }
  const ordered: TWorkshopCandidate[] = [];
  for (const candidate of candidates) {
    const insertionIndex = ordered.findIndex((existing) =>
      candidate.workshopStartsAt === existing.workshopStartsAt
        ? candidate.trainerName.localeCompare(existing.trainerName) < 0
        : candidate.workshopStartsAt < existing.workshopStartsAt
    );
    if (insertionIndex === -1) ordered.push(candidate);
    else ordered.splice(insertionIndex, 0, candidate);
  }
  return ordered;
}

/**
 * A hold's start or expiry, as a short weekday-date-time label.
 *
 * The time is spelled out field by field rather than with `timeStyle`. ECMA-402
 * treats `dateStyle`/`timeStyle` as shorthands that cannot be mixed with the
 * individual field options, and rejects the combination with a TypeError rather
 * than merging them -- which is what this threw on every render showing a hold.
 */
export const dateTimeLabel = (value: string, locales?: Intl.LocalesArgument) =>
  new Date(value).toLocaleString(locales, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

/** How far forward "find the first free slot" will look before giving up. */
export const FIRST_AVAILABLE_WINDOWS = 8;
/** The endpoint refuses a range longer than this, so the walk steps by it. */
export const CAPACITY_WINDOW_DAYS = 14;

export type TWorkshopSearchSpec = {
  trainerIds: string[];
  durationMinutes: number;
  preparationMinutes: number;
  travelBeforeMinutes: number;
  travelAfterMinutes: number;
};

export type TFirstAvailable =
  | { found: true; candidate: TWorkshopCandidate; windowStart: Date; windowEnd: Date; windowsSearched: number }
  | { found: false; windowsSearched: number; searchedUntil: Date };

export function windowAfter(start: Date, index: number): { windowStart: Date; windowEnd: Date } {
  const windowStart = new Date(start.getTime() + index * CAPACITY_WINDOW_DAYS * 86_400_000);
  return { windowStart, windowEnd: new Date(windowStart.getTime() + CAPACITY_WINDOW_DAYS * 86_400_000) };
}

/**
 * The first slot that fits, looking forward from a given week.
 *
 * The planner can only answer "every slot in the week on screen", because that
 * is the one window it has fetched. The question a coordinator actually has is
 * "when is the next possible date?", and answering it means looking past that
 * window.
 *
 * It walks forward in fourteen-day steps because `GET /capacity/` refuses a
 * longer range, and **sequentially** because that endpoint is throttled per user
 * and per workspace -- firing eight requests at once is the reliable way to be
 * rate-limited. Sequential also means a hit in the first window costs one
 * request rather than eight.
 *
 * `fetchWindow` is injected so the walk can be tested without a server, and so
 * the caller can route it through its own SWR cache: a window already on screen
 * costs nothing to revisit.
 */
export async function findFirstAvailable(
  from: Date,
  spec: TWorkshopSearchSpec,
  fetchWindow: (windowStart: Date, windowEnd: Date) => Promise<TTrainerCapacity[]>,
  options: { maxWindows?: number; onProgress?: (windowStart: Date, index: number) => void } = {}
): Promise<TFirstAvailable> {
  const maxWindows = options.maxWindows ?? FIRST_AVAILABLE_WINDOWS;

  for (let index = 0; index < maxWindows; index++) {
    const { windowStart, windowEnd } = windowAfter(from, index);
    options.onProgress?.(windowStart, index);

    // Sequential on purpose: the capacity endpoint is throttled per user and per
    // workspace, so firing every window at once is the reliable way to be refused.
    // It also means a hit in the first window costs one request rather than eight.
    // oxlint-disable-next-line no-await-in-loop
    const trainers = await fetchWindow(windowStart, windowEnd);
    const candidates = findWorkshopCandidates(
      trainers,
      spec.trainerIds,
      windowStart,
      windowEnd,
      spec.durationMinutes,
      spec.preparationMinutes,
      spec.travelBeforeMinutes,
      spec.travelAfterMinutes
    );

    // Candidates are already ordered by start time, then trainer name, so the
    // earliest for any trainer is simply the first one.
    if (candidates.length) {
      return { found: true, candidate: candidates[0], windowStart, windowEnd, windowsSearched: index + 1 };
    }
  }

  return { found: false, windowsSearched: maxWindows, searchedUntil: windowAfter(from, maxWindows).windowStart };
}
