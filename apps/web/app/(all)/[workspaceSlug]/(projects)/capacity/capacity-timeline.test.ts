/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import {
  CAPACITY_INTERVAL_LAYERS,
  availableRanges,
  dayBounds,
  intervalLabel,
  intervalPosition,
  rangeMinutes,
} from "./capacity-timeline.utils";

describe("capacity timeline", () => {
  it("clips an interval to the visible day", () => {
    const dayStart = new Date("2026-09-07T00:00:00.000Z");
    const dayEnd = new Date("2026-09-08T00:00:00.000Z");

    expect(
      intervalPosition({ start: "2026-09-06T18:00:00.000Z", end: "2026-09-07T06:00:00.000Z" }, dayStart, dayEnd)
    ).toEqual({ left: "0%", width: "25%" });
  });

  it("uses calendar boundaries rather than fixed milliseconds", () => {
    const monday = new Date(2026, 8, 7, 0, 0, 0, 0);
    const bounds = dayBounds(monday, 6);

    expect(bounds.start.getDay()).toBe(0);
    expect(bounds.end.getDay()).toBe(1);
    expect(bounds.start.getHours()).toBe(0);
    expect(bounds.end.getHours()).toBe(0);
  });

  it("does not invent restricted workshop details", () => {
    expect(
      intervalLabel({
        kind: "workshop",
        start: "2026-09-07T09:00:00Z",
        end: "2026-09-07T10:00:00Z",
        work_item: null,
      })
    ).toBe("Workshop (details restricted)");
  });

  it("renders working time below busy time and workshops", () => {
    expect(CAPACITY_INTERVAL_LAYERS).toEqual(["working", "google_busy", "workshop"]);
  });

  it("labels Google intervals without exposing event details", () => {
    expect(
      intervalLabel({
        kind: "google_busy",
        start: "2026-09-07T09:00:00Z",
        end: "2026-09-07T10:00:00Z",
      })
    ).toBe("Busy — Google Calendar");
  });

  it("returns the exact free ranges inside working time", () => {
    const dayStart = new Date("2026-09-07T00:00:00.000Z");
    const dayEnd = new Date("2026-09-08T00:00:00.000Z");
    const ranges = availableRanges(
      [
        { kind: "working", start: "2026-09-07T09:00:00.000Z", end: "2026-09-07T22:00:00.000Z" },
        { kind: "google_busy", start: "2026-09-07T10:00:00.000Z", end: "2026-09-07T12:00:00.000Z" },
        { kind: "workshop", start: "2026-09-07T14:00:00.000Z", end: "2026-09-07T18:00:00.000Z" },
      ],
      dayStart,
      dayEnd
    );

    expect(ranges).toEqual([
      { start: "2026-09-07T09:00:00.000Z", end: "2026-09-07T10:00:00.000Z" },
      { start: "2026-09-07T12:00:00.000Z", end: "2026-09-07T14:00:00.000Z" },
      { start: "2026-09-07T18:00:00.000Z", end: "2026-09-07T22:00:00.000Z" },
    ]);
    expect(rangeMinutes(ranges)).toBe(420);
  });

  it("merges overlapping blockers before subtracting them", () => {
    const ranges = availableRanges(
      [
        { kind: "working", start: "2026-09-07T09:00:00.000Z", end: "2026-09-07T17:00:00.000Z" },
        { kind: "google_busy", start: "2026-09-07T10:00:00.000Z", end: "2026-09-07T13:00:00.000Z" },
        { kind: "workshop", start: "2026-09-07T12:00:00.000Z", end: "2026-09-07T15:00:00.000Z" },
      ],
      new Date("2026-09-07T00:00:00.000Z"),
      new Date("2026-09-08T00:00:00.000Z")
    );

    expect(ranges).toEqual([
      { start: "2026-09-07T09:00:00.000Z", end: "2026-09-07T10:00:00.000Z" },
      { start: "2026-09-07T15:00:00.000Z", end: "2026-09-07T17:00:00.000Z" },
    ]);
  });
});
