/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { TZDate } from "@date-fns/tz";
import type { TTrainerCapacity } from "@/services/capacity.service";
import { availableRanges } from "../shared/capacity-timeline.utils";

export type TWorkshopCandidate = {
  trainerId: string;
  trainerName: string;
  timezone: string;
  workshopStartsAt: string;
  workshopEndsAt: string;
  blockedStartsAt: string;
  blockedEndsAt: string;
};

/**
 * Whether the planner may offer this trainer's time.
 *
 * Only a fresh read of a connected calendar counts. Hangar reads each trainer's
 * Google calendar with that trainer's own credential, so a trainer who never
 * connected one comes back with no busy intervals at all -- which is not "this
 * week is free", it is "we cannot see this week". Offering their booking hours
 * as candidates is how the planner ends up proposing someone who is already
 * booked all Tuesday, and a coordinator cannot tell the two apart from a card.
 *
 * `stale`, `rate_limited`, `provider_unavailable` and the `training_*` statuses
 * are held out for the same reason: what we have is not what the calendar
 * currently says. Those the server also refuses at booking time, so offering
 * them was offering a card whose hold comes back 503. `not_connected` it does
 * not refuse -- `booking_preflight` only demands a fresh read from a trainer who
 * has a calendar selection -- so for that one this filter is the whole check.
 */
export const canOfferTrainer = (trainer: TTrainerCapacity) => trainer.availability_status === "fresh";

/** Which half of the day a workshop may start in. */
export type TStartWindow = "any" | "morning" | "afternoon";

/** The workshop, the buffers around it, and when it may start. */
export type TWorkshopSpec = {
  trainerIds: string[];
  durationMinutes: number;
  preparationMinutes: number;
  travelBeforeMinutes: number;
  travelAfterMinutes: number;
  startWindow?: TStartWindow;
  timeZone?: string;
  /** Earliest allowed start of preparation/travel, not just the workshop. */
  notBefore?: Date;
};

/**
 * How far apart two offered starts in the same free range are.
 *
 * Half an hour, and on the half hour, because that is how the times get said
 * out loud -- nobody books a workshop for 09:07, which is what a range that
 * opens when a calendar block closes would otherwise offer.
 */
export const SLOT_STEP_MINUTES = 30;

/**
 * How many starts one trainer is offered on one day.
 *
 * Without a cap a trainer free from nine to ten at night yields two dozen cards
 * that all say the same thing, and the grid stops being readable long before
 * that. Four spread across the day answers "when could she do it?" better than
 * twenty-four consecutive half hours do.
 */
export const MAX_SLOTS_PER_TRAINER_PER_DAY = 4;

/** The local day an instant falls in, as a key that sorts. */
const dayKey = (value: Date) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;

function startsInWindow(workshopStart: Date, startWindow: TStartWindow) {
  if (startWindow === "any") return true;
  const hour = workshopStart.getHours();
  return startWindow === "morning" ? hour < 12 : hour >= 12;
}

/**
 * At most `max` items, keeping the first and spreading the rest.
 *
 * Taking the first `max` would hand back four consecutive half hours of the same
 * morning and call it a choice. The first is kept whatever happens, because the
 * earliest fit is the answer to a question people actually ask -- and because
 * `findFirstAvailable` reads it.
 */
function spread<T>(items: T[], max: number): T[] {
  if (items.length <= max) return items;
  if (max <= 1) return items.slice(0, Math.max(0, max));
  const step = (items.length - 1) / (max - 1);
  return Array.from({ length: max }, (_, index) => items[Math.round(index * step)]);
}

/**
 * Every start worth offering inside one free range.
 *
 * The range's own start comes first and unaligned, because it is the genuine
 * earliest fit and rounding it away would make the planner answer a slightly
 * different question than the one it is asked. Everything after it sits on the
 * half hour.
 */
function startsInRange(
  rangeStart: Date,
  rangeEnd: Date,
  totalMinutes: number,
  beforeMinutes: number,
  timeZone?: string
): Date[] {
  const totalMs = totalMinutes * 60_000;
  const stepMs = SLOT_STEP_MINUTES * 60_000;
  const latest = rangeEnd.getTime() - totalMs;
  if (latest < rangeStart.getTime()) return [];

  const starts = [new Date(rangeStart)];
  // Align the workshop start: a 15-minute preparation must not hide a noon workshop.
  const beforeMs = beforeMinutes * 60_000;
  const aligned = new TZDate(rangeStart.getTime() + beforeMs, timeZone);
  aligned.setSeconds(0, 0);
  aligned.setMinutes(Math.ceil(aligned.getMinutes() / SLOT_STEP_MINUTES) * SLOT_STEP_MINUTES);
  for (let time = aligned.getTime() - beforeMs; time <= latest; time += stepMs) {
    if (time > rangeStart.getTime()) starts.push(new Date(time));
  }
  return starts;
}

export function findWorkshopCandidates(
  trainers: TTrainerCapacity[],
  windowStart: Date,
  windowEnd: Date,
  spec: TWorkshopSpec
): TWorkshopCandidate[] {
  const { durationMinutes, preparationMinutes, travelBeforeMinutes, travelAfterMinutes } = spec;
  const beforeMinutes = preparationMinutes + travelBeforeMinutes;
  const totalMinutes = beforeMinutes + durationMinutes + travelAfterMinutes;
  if (durationMinutes <= 0 || totalMinutes <= 0 || windowStart >= windowEnd) return [];
  const startWindow = spec.startWindow ?? "any";
  const earliest = new Date(Math.max(windowStart.getTime(), spec.notBefore?.getTime() ?? windowStart.getTime()));
  const selected = new Set(spec.trainerIds);
  const candidates: TWorkshopCandidate[] = [];

  for (const trainer of trainers) {
    if (!selected.has(trainer.trainer_id)) continue;
    if (!canOfferTrainer(trainer)) continue;
    // Per trainer per day, because the cap is about how much choice one person
    // is offered for one date -- not about the size of the grid.
    const byDay = new Map<string, TWorkshopCandidate[]>();
    for (const range of availableRanges(trainer.intervals, earliest, windowEnd)) {
      for (const blockedStart of startsInRange(
        new Date(range.start),
        new Date(range.end),
        totalMinutes,
        beforeMinutes,
        spec.timeZone
      )) {
        const workshopStart = new TZDate(blockedStart.getTime() + beforeMinutes * 60_000, spec.timeZone);
        if (!startsInWindow(workshopStart, startWindow)) continue;
        const day = byDay.get(dayKey(workshopStart)) ?? [];
        day.push({
          trainerId: trainer.trainer_id,
          trainerName: trainer.display_name,
          timezone: trainer.timezone,
          workshopStartsAt: new Date(workshopStart.getTime()).toISOString(),
          workshopEndsAt: new Date(workshopStart.getTime() + durationMinutes * 60_000).toISOString(),
          blockedStartsAt: blockedStart.toISOString(),
          blockedEndsAt: new Date(blockedStart.getTime() + totalMinutes * 60_000).toISOString(),
        });
        byDay.set(dayKey(workshopStart), day);
      }
    }
    for (const day of byDay.values()) candidates.push(...spread(day, MAX_SLOTS_PER_TRAINER_PER_DAY));
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

/** Leave time to select a slot instead of offering a block that has already started on click. */
export const nextBookingMinute = (now: Date) => new Date((Math.floor(now.getTime() / 60_000) + 1) * 60_000);

/** Explain the physical fit independently of the number of cards offered. */
export function workshopAvailability(
  trainers: TTrainerCapacity[],
  windowStart: Date,
  windowEnd: Date,
  spec: TWorkshopSpec
) {
  const bufferMinutes = spec.preparationMinutes + spec.travelBeforeMinutes + spec.travelAfterMinutes;
  const earliest = new Date(Math.max(windowStart.getTime(), spec.notBefore?.getTime() ?? windowStart.getTime()));
  const selectedIds = new Set(spec.trainerIds);
  // Measured over the trainers the search actually walks. Counting an
  // unconnected trainer's booking hours here would answer "the longest opening
  // is seven hours" about time no card was ever offered for.
  const ticked = trainers.filter((trainer) => selectedIds.has(trainer.trainer_id));
  const selected = ticked.filter(canOfferTrainer);
  let longestFreeMinutes = 0;
  for (const trainer of selected) {
    for (const range of availableRanges(trainer.intervals, earliest, windowEnd)) {
      longestFreeMinutes = Math.max(
        longestFreeMinutes,
        Math.floor((new Date(range.end).getTime() - new Date(range.start).getTime()) / 60_000)
      );
    }
  }
  return {
    bufferMinutes,
    requiredMinutes: spec.durationMinutes + bufferMinutes,
    longestFreeMinutes,
    selectedTrainerCount: selected.length,
    /** Ticked, but with no calendar the planner can read. */
    unverifiedTrainerCount: ticked.length - selected.length,
  };
}

/** An empty search should explain which requirement prevents a fit. */
export function noWorkshopFitReason(
  availability: ReturnType<typeof workshopAvailability>,
  spec: TWorkshopSpec,
  formatDuration: (minutes: number) => string
): string {
  if (!spec.trainerIds.length) return "Select at least one trainer to see available times.";
  if (spec.durationMinutes < 15) return "Enter a workshop duration of at least 15 minutes.";
  if (!availability.selectedTrainerCount) {
    // Two different dead ends, and telling someone to "choose an active trainer"
    // when the trainer is active and simply has no calendar connected sends
    // them looking in the wrong place.
    if (availability.unverifiedTrainerCount)
      return "No selected trainer has a calendar Hangar can read, so there is no availability to offer. Ask them to connect Google on their own capacity page, or select someone who already has.";
    return "The selected trainers are no longer available. Choose an active trainer.";
  }
  if (!availability.longestFreeMinutes) {
    return "No free booking hours remain in this range. Check the trainers’ booking hours and calendar blocks, or look further ahead.";
  }
  if (availability.longestFreeMinutes < availability.requiredMinutes) {
    return `This plan needs ${formatDuration(availability.requiredMinutes)} without a break, including preparation and travel. The longest free opening is ${formatDuration(availability.longestFreeMinutes)}. Adjust the duration or buffers, or look further ahead.`;
  }
  return "No workshop starts fit that half of the day. Try Any time or look further ahead.";
}

/** Candidates split into the days they start on, in order. */
export function groupByDay(
  candidates: TWorkshopCandidate[],
  timeZone?: string
): Array<{ day: string; candidates: TWorkshopCandidate[] }> {
  const days: Array<{ day: string; candidates: TWorkshopCandidate[] }> = [];
  for (const candidate of candidates) {
    const day = dayKey(new TZDate(candidate.workshopStartsAt, timeZone));
    const last = days.at(-1);
    if (last && last.day === day) last.candidates.push(candidate);
    else days.push({ day, candidates: [candidate] });
  }
  return days;
}

/** A time of day, with no date. The day heading above the card carries that. */
export const timeLabel = (value: string, locales?: Intl.LocalesArgument, timeZone?: string) =>
  new Date(value).toLocaleTimeString(locales, { hour: "2-digit", minute: "2-digit", timeZone });

/** Whether two instants fall on the same local day. */
export const sameLocalDay = (left: string, right: string, timeZone?: string) =>
  dayKey(new TZDate(left, timeZone)) === dayKey(new TZDate(right, timeZone));

/** A day heading: the weekday and the date, without a time. */
export const dayLabel = (value: string, locales?: Intl.LocalesArgument, timeZone?: string) =>
  new Date(value).toLocaleDateString(locales, { weekday: "long", day: "numeric", month: "long", timeZone });

/**
 * A hold's start or expiry, as a short weekday-date-time label.
 *
 * The time is spelled out field by field rather than with `timeStyle`. ECMA-402
 * treats `dateStyle`/`timeStyle` as shorthands that cannot be mixed with the
 * individual field options, and rejects the combination with a TypeError rather
 * than merging them -- which is what this threw on every render showing a hold.
 */
export const dateTimeLabel = (value: string, locales?: Intl.LocalesArgument, timeZone?: string) =>
  new Date(value).toLocaleString(locales, {
    timeZone,
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

export type TFirstAvailable =
  | { found: true; candidate: TWorkshopCandidate; windowStart: Date; windowEnd: Date; windowsSearched: number }
  | {
      found: false;
      windowsSearched: number;
      searchedUntil: Date;
      availability: ReturnType<typeof workshopAvailability>;
    };

export function windowAfter(start: Date, index: number): { windowStart: Date; windowEnd: Date } {
  if (!(start instanceof TZDate)) {
    const windowStart = new Date(start.getTime() + index * CAPACITY_WINDOW_DAYS * 86_400_000);
    return { windowStart, windowEnd: new Date(windowStart.getTime() + CAPACITY_WINDOW_DAYS * 86_400_000) };
  }
  const windowStart = new TZDate(start.getTime(), start.timeZone);
  windowStart.setDate(windowStart.getDate() + index * CAPACITY_WINDOW_DAYS);
  const windowEnd = new TZDate(windowStart.getTime(), windowStart.timeZone);
  windowEnd.setDate(windowEnd.getDate() + CAPACITY_WINDOW_DAYS);
  return { windowStart, windowEnd };
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
  spec: TWorkshopSpec,
  fetchWindow: (windowStart: Date, windowEnd: Date) => Promise<TTrainerCapacity[]>,
  options: { maxWindows?: number; onProgress?: (windowStart: Date, index: number) => void; signal?: AbortSignal } = {}
): Promise<TFirstAvailable> {
  const maxWindows = options.maxWindows ?? FIRST_AVAILABLE_WINDOWS;
  const availability = workshopAvailability([], from, from, spec);

  for (let index = 0; index < maxWindows; index++) {
    options.signal?.throwIfAborted();
    const { windowStart, windowEnd } = windowAfter(from, index);
    options.onProgress?.(windowStart, index);

    // Sequential on purpose: the capacity endpoint is throttled per user and per
    // workspace, so firing every window at once is the reliable way to be refused.
    // It also means a hit in the first window costs one request rather than eight.
    // oxlint-disable-next-line no-await-in-loop
    const trainers = await fetchWindow(windowStart, windowEnd);
    options.signal?.throwIfAborted();
    const current = workshopAvailability(trainers, windowStart, windowEnd, spec);
    availability.longestFreeMinutes = Math.max(availability.longestFreeMinutes, current.longestFreeMinutes);
    availability.selectedTrainerCount = Math.max(availability.selectedTrainerCount, current.selectedTrainerCount);
    const candidates = findWorkshopCandidates(trainers, windowStart, windowEnd, spec);

    // Candidates are already ordered by start time, then trainer name, so the
    // earliest for any trainer is simply the first one.
    if (candidates.length) {
      return { found: true, candidate: candidates[0], windowStart, windowEnd, windowsSearched: index + 1 };
    }
  }

  return {
    found: false,
    windowsSearched: maxWindows,
    searchedUntil: windowAfter(from, maxWindows).windowStart,
    availability,
  };
}

export const planSignature = (plan: import("@/services/capacity.service").TWorkshopPlanDraftInput) =>
  JSON.stringify({
    ...plan,
    // ES2022 is the web app's current target; the copied array keeps sort() mutation local.
    // oxlint-disable-next-line unicorn/no-array-sort
    trainer_ids: [...plan.trainer_ids].sort(),
  });
