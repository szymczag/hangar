/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import type { TTrainerCapacity } from "@/services/capacity.service";
import {
  dateTimeLabel,
  findFirstAvailable,
  findWorkshopCandidates,
  groupByDay,
  MAX_SLOTS_PER_TRAINER_PER_DAY,
  timeLabel,
} from "./workshop-planner.utils";
import { planSignature } from "./workshop-planner";

const trainer = {
  trainer_id: "trainer-1",
  display_name: "A Trainer",
  timezone: "Europe/Warsaw",
  connection_status: "connected",
  availability_status: "fresh",
  working_minutes: 480,
  google_busy_minutes: 60,
  workshop_minutes: 0,
  hold_minutes: 0,
  unavailable_minutes: 60,
  available_minutes: 420,
  intervals: [
    { start: "2026-09-07T07:00:00.000Z", end: "2026-09-07T15:00:00.000Z", kind: "working" },
    { start: "2026-09-07T09:00:00.000Z", end: "2026-09-07T10:00:00.000Z", kind: "google_busy" },
  ],
  conflicts: [],
} satisfies TTrainerCapacity;

/**
 * Fixtures are built with the local `Date` constructor rather than UTC literals.
 * Which starts are offered, which day they are grouped under and which half of
 * the day they fall in are all questions about the viewer's clock, so pinning
 * them to UTC would pass here and fail wherever the suite runs in another zone.
 */
const at = (day: number, hour: number, minute = 0) => new Date(2026, 8, day, hour, minute, 0, 0);
const freeBetween = (...spans: Array<[Date, Date]>): TTrainerCapacity => ({
  ...trainer,
  intervals: spans.map(([from, to]) => ({ start: from.toISOString(), end: to.toISOString(), kind: "working" })),
});
const startTimes = (candidates: ReturnType<typeof findWorkshopCandidates>) =>
  candidates.map((candidate) => timeLabel(candidate.workshopStartsAt, "en-GB"));

describe("findWorkshopCandidates", () => {
  const spec = {
    trainerIds: [trainer.trainer_id],
    durationMinutes: 120,
    preparationMinutes: 30,
    travelBeforeMinutes: 60,
    travelAfterMinutes: 45,
  };

  it("fits preparation and both travel buffers inside a genuinely free range", () => {
    const result = findWorkshopCandidates(
      [trainer],
      new Date("2026-09-07T00:00:00.000Z"),
      new Date("2026-09-08T00:00:00.000Z"),
      spec
    );

    // The 07:00-09:00 opening is two hours and the whole block is 4h15, so only
    // the one after the busy range can hold it.
    expect(result[0]).toEqual({
      trainerId: "trainer-1",
      trainerName: "A Trainer",
      timezone: "Europe/Warsaw",
      availabilityStatus: "fresh",
      blockedStartsAt: "2026-09-07T10:00:00.000Z",
      workshopStartsAt: "2026-09-07T11:30:00.000Z",
      workshopEndsAt: "2026-09-07T13:30:00.000Z",
      blockedEndsAt: "2026-09-07T14:15:00.000Z",
    });
  });

  it("does not suggest unselected trainers or ranges too short for the whole block", () => {
    expect(
      findWorkshopCandidates([trainer], new Date("2026-09-07T00:00:00.000Z"), new Date("2026-09-08T00:00:00.000Z"), {
        ...spec,
        trainerIds: [],
      })
    ).toEqual([]);
    expect(
      findWorkshopCandidates([trainer], new Date("2026-09-07T09:00:00.000Z"), new Date("2026-09-07T10:00:00.000Z"), {
        ...spec,
        durationMinutes: 60,
        preparationMinutes: 0,
        travelBeforeMinutes: 0,
        travelAfterMinutes: 0,
      })
    ).toEqual([]);
  });

  it("offers more than the first fit in an opening, so an afternoon can be asked for", () => {
    // The whole point of the change: 09:00-17:00 with a two-hour block used to
    // yield exactly one card, at 09:00, and no way to express "later".
    const result = findWorkshopCandidates([freeBetween([at(7, 9), at(7, 17)])], at(7, 0), at(8, 0), {
      trainerIds: [trainer.trainer_id],
      durationMinutes: 120,
      preparationMinutes: 0,
      travelBeforeMinutes: 0,
      travelAfterMinutes: 0,
    });

    expect(result.length).toBeGreaterThan(1);
    expect(startTimes(result)[0]).toBe("09:00");
  });

  it("keeps the genuine earliest start when an opening does not begin on the half hour", () => {
    // A range that opens when a calendar block closes can start at 09:07. That
    // is the real earliest fit and `findFirstAvailable` reads it, so it is kept
    // as-is; everything after it is said the way people say times.
    // Narrow enough that four fits exist, so the day cap does not thin them and
    // hide the stepping this is about.
    const result = findWorkshopCandidates([freeBetween([at(7, 9, 7), at(7, 11, 30)])], at(7, 0), at(8, 0), {
      trainerIds: [trainer.trainer_id],
      durationMinutes: 60,
      preparationMinutes: 0,
      travelBeforeMinutes: 0,
      travelAfterMinutes: 0,
    });

    expect(startTimes(result)).toEqual(["09:07", "09:30", "10:00", "10:30"]);
  });

  it("caps one trainer's starts for one day, keeping the earliest and spreading the rest", () => {
    const result = findWorkshopCandidates([freeBetween([at(7, 8), at(7, 22)])], at(7, 0), at(8, 0), {
      trainerIds: [trainer.trainer_id],
      durationMinutes: 60,
      preparationMinutes: 0,
      travelBeforeMinutes: 0,
      travelAfterMinutes: 0,
    });

    // Twenty-seven half-hourly fits, offered as four spread across the day
    // rather than four consecutive ones at breakfast. The earliest and the
    // latest are both kept, so the pair bounds what is actually possible.
    expect(result).toHaveLength(MAX_SLOTS_PER_TRAINER_PER_DAY);
    expect(startTimes(result)).toEqual(["08:00", "12:30", "16:30", "21:00"]);
  });

  it("counts the cap per day, not per week", () => {
    const result = findWorkshopCandidates(
      [freeBetween([at(7, 9), at(7, 17)], [at(8, 9), at(8, 17)])],
      at(7, 0),
      at(9, 0),
      {
        trainerIds: [trainer.trainer_id],
        durationMinutes: 60,
        preparationMinutes: 0,
        travelBeforeMinutes: 0,
        travelAfterMinutes: 0,
      }
    );

    expect(result).toHaveLength(MAX_SLOTS_PER_TRAINER_PER_DAY * 2);
    expect(groupByDay(result).map((group) => group.candidates.length)).toEqual([
      MAX_SLOTS_PER_TRAINER_PER_DAY,
      MAX_SLOTS_PER_TRAINER_PER_DAY,
    ]);
  });

  it("narrows to the half of the day it is asked about", () => {
    const base = {
      trainerIds: [trainer.trainer_id],
      durationMinutes: 60,
      preparationMinutes: 0,
      travelBeforeMinutes: 0,
      travelAfterMinutes: 0,
    };
    const open = [freeBetween([at(7, 9), at(7, 17)])];

    const morning = findWorkshopCandidates(open, at(7, 0), at(8, 0), { ...base, startWindow: "morning" });
    const afternoon = findWorkshopCandidates(open, at(7, 0), at(8, 0), { ...base, startWindow: "afternoon" });

    expect(morning.length).toBeGreaterThan(0);
    expect(afternoon.length).toBeGreaterThan(0);
    for (const candidate of morning) {
      expect(new Date(candidate.workshopStartsAt).getHours()).toBeLessThan(12);
    }
    for (const candidate of afternoon) {
      expect(new Date(candidate.workshopStartsAt).getHours()).toBeGreaterThanOrEqual(12);
    }
  });

  it("measures the start window from the workshop, not from the travel before it", () => {
    // An afternoon workshop with an hour of travel in front of it starts in the
    // afternoon even though the trainer's day starts before noon. Filtering on
    // the blocked start would hide it.
    const result = findWorkshopCandidates([freeBetween([at(7, 11), at(7, 17)])], at(7, 0), at(8, 0), {
      trainerIds: [trainer.trainer_id],
      durationMinutes: 60,
      preparationMinutes: 0,
      travelBeforeMinutes: 60,
      travelAfterMinutes: 0,
      startWindow: "afternoon",
    });

    expect(startTimes(result)[0]).toBe("12:00");
    expect(timeLabel(result[0].blockedStartsAt, "en-GB")).toBe("11:00");
  });
});

describe("groupByDay", () => {
  it("splits candidates into the local days they start on, in order", () => {
    const candidates = findWorkshopCandidates(
      [freeBetween([at(7, 9), at(7, 12)], [at(9, 9), at(9, 12)])],
      at(7, 0),
      at(10, 0),
      {
        trainerIds: [trainer.trainer_id],
        durationMinutes: 60,
        preparationMinutes: 0,
        travelBeforeMinutes: 0,
        travelAfterMinutes: 0,
      }
    );

    const days = groupByDay(candidates);

    expect(days.map((group) => group.day)).toEqual(["2026-09-07", "2026-09-09"]);
    expect(days.flatMap((group) => group.candidates)).toEqual(candidates);
  });

  it("has nothing to group when there is nothing to offer", () => {
    expect(groupByDay([])).toEqual([]);
  });
});

describe("dateTimeLabel", () => {
  // The shipped version passed `timeStyle` alongside `weekday`/`day`/`month`.
  // ECMA-402 treats the shorthands as exclusive of the individual field options
  // and throws a TypeError rather than merging them, so every render showing a
  // hold died. It threw in every locale, which is why this asserts across three
  // rather than trusting one -- and it calls the real helper, so it fails if
  // the invalid combination ever comes back.
  it.each(["pl-PL", "en-US", "de-DE"])("renders a date and a time in %s", (locale) => {
    const label = dateTimeLabel("2026-09-10T14:30:00.000Z", locale);

    // A date part and a time part, rather than an exact string: the wording is
    // ICU's to decide, and pinning it would test the runtime instead of this.
    expect(label).toMatch(/\d{1,2}/);
    expect(label).toMatch(/\d{1,2}[:.]\d{2}/);
  });

  it("uses the runtime locale when none is given", () => {
    expect(() => dateTimeLabel("2026-09-10T14:30:00.000Z")).not.toThrow();
  });
});

describe("findFirstAvailable", () => {
  const spec = {
    trainerIds: [trainer.trainer_id],
    durationMinutes: 120,
    preparationMinutes: 30,
    travelBeforeMinutes: 60,
    travelAfterMinutes: 45,
  };
  const busyTrainer = { ...trainer, intervals: [] } satisfies TTrainerCapacity;

  it("stops at the first window that has a slot, and does not look further", async () => {
    const asked: string[] = [];
    const result = await findFirstAvailable(new Date("2026-09-07T00:00:00.000Z"), spec, async (windowStart) => {
      asked.push(windowStart.toISOString());
      return [trainer];
    });

    expect(result.found).toBe(true);
    expect(asked).toHaveLength(1);
  });

  it("walks forward when earlier windows are empty", async () => {
    const asked: string[] = [];
    // The fixture trainer is only free on 2026-09-07, so "free in the third
    // window" has to be built by moving those hours into that window rather than
    // by handing back the same trainer and hoping.
    const freeInside = (windowStart: Date): TTrainerCapacity => ({
      ...trainer,
      intervals: [
        {
          start: new Date(windowStart.getTime() + 7 * 3_600_000).toISOString(),
          end: new Date(windowStart.getTime() + 15 * 3_600_000).toISOString(),
          kind: "working",
        },
      ],
    });
    const result = await findFirstAvailable(new Date("2026-09-07T00:00:00.000Z"), spec, async (windowStart) => {
      asked.push(windowStart.toISOString());
      return asked.length === 3 ? [freeInside(windowStart)] : [busyTrainer];
    });

    expect(result.found).toBe(true);
    if (result.found) expect(result.windowsSearched).toBe(3);
    expect(asked).toHaveLength(3);
    // Fourteen-day steps, because the endpoint refuses a longer range.
    expect(asked[1]).toBe("2026-09-21T00:00:00.000Z");
    expect(asked[2]).toBe("2026-10-05T00:00:00.000Z");
  });

  it("gives up honestly rather than looping", async () => {
    const result = await findFirstAvailable(new Date("2026-09-07T00:00:00.000Z"), spec, async () => [busyTrainer], {
      maxWindows: 4,
    });

    expect(result.found).toBe(false);
    if (!result.found) {
      expect(result.windowsSearched).toBe(4);
      expect(result.searchedUntil.toISOString()).toBe("2026-11-02T00:00:00.000Z");
    }
  });

  it("fetches one window at a time, because the endpoint is throttled", async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    await findFirstAvailable(
      new Date("2026-09-07T00:00:00.000Z"),
      spec,
      async () => {
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await new Promise((resolve) => setTimeout(resolve, 1));
        inFlight -= 1;
        return [busyTrainer];
      },
      { maxWindows: 5 }
    );

    expect(maxInFlight).toBe(1);
  });

  it("answers for one trainer when asked for one trainer", async () => {
    const other = { ...trainer, trainer_id: "trainer-2", display_name: "B Trainer" } satisfies TTrainerCapacity;
    const result = await findFirstAvailable(
      new Date("2026-09-07T00:00:00.000Z"),
      { ...spec, trainerIds: [other.trainer_id] },
      async () => [trainer, other]
    );

    expect(result.found).toBe(true);
    if (result.found) expect(result.candidate.trainerId).toBe("trainer-2");
  });
});

describe("planSignature", () => {
  const plan = {
    title: "NetSec workshop",
    duration_minutes: 240,
    preparation_minutes: 30,
    travel_before_minutes: 60,
    travel_after_minutes: 60,
    trainer_ids: ["trainer-2", "trainer-1"],
  };

  it("does not care in which order the eligible trainers were ticked", () => {
    expect(planSignature(plan)).toBe(planSignature({ ...plan, trainer_ids: ["trainer-1", "trainer-2"] }));
  });

  it("changes when the plan itself changes", () => {
    expect(planSignature(plan)).not.toBe(planSignature({ ...plan, duration_minutes: 300 }));
    expect(planSignature(plan)).not.toBe(planSignature({ ...plan, trainer_ids: ["trainer-1"] }));
  });
});
