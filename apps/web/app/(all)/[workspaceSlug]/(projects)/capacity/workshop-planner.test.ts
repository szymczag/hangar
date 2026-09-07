/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { describe, expect, it } from "vitest";
import type { TTrainerCapacity } from "@/services/capacity.service";
import { findWorkshopCandidates } from "./workshop-planner.utils";

const trainer = {
  trainer_id: "trainer-1",
  display_name: "A Trainer",
  timezone: "Europe/Warsaw",
  connection_status: "connected",
  availability_status: "fresh",
  working_minutes: 480,
  google_busy_minutes: 60,
  workshop_minutes: 0,
  unavailable_minutes: 60,
  available_minutes: 420,
  intervals: [
    { start: "2026-09-07T07:00:00.000Z", end: "2026-09-07T15:00:00.000Z", kind: "working" },
    { start: "2026-09-07T09:00:00.000Z", end: "2026-09-07T10:00:00.000Z", kind: "google_busy" },
  ],
  conflicts: [],
} satisfies TTrainerCapacity;

describe("findWorkshopCandidates", () => {
  it("fits preparation and both travel buffers inside a genuinely free range", () => {
    const result = findWorkshopCandidates(
      [trainer],
      [trainer.trainer_id],
      new Date("2026-09-07T00:00:00.000Z"),
      new Date("2026-09-08T00:00:00.000Z"),
      120,
      30,
      60,
      45
    );

    expect(result).toEqual([
      {
        trainerId: "trainer-1",
        trainerName: "A Trainer",
        timezone: "Europe/Warsaw",
        availabilityStatus: "fresh",
        blockedStartsAt: "2026-09-07T10:00:00.000Z",
        workshopStartsAt: "2026-09-07T11:30:00.000Z",
        workshopEndsAt: "2026-09-07T13:30:00.000Z",
        blockedEndsAt: "2026-09-07T14:15:00.000Z",
      },
    ]);
  });

  it("does not suggest unselected trainers or ranges too short for the whole block", () => {
    expect(
      findWorkshopCandidates(
        [trainer],
        [],
        new Date("2026-09-07T00:00:00.000Z"),
        new Date("2026-09-08T00:00:00.000Z"),
        60,
        0,
        0,
        0
      )
    ).toEqual([]);
    expect(
      findWorkshopCandidates(
        [trainer],
        [trainer.trainer_id],
        new Date("2026-09-07T09:00:00.000Z"),
        new Date("2026-09-07T10:00:00.000Z"),
        60,
        0,
        0,
        0
      )
    ).toEqual([]);
  });
});
