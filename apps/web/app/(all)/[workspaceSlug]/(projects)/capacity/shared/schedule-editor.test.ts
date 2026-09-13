// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only
import { describe, expect, it } from "vitest";
import { copyBookingDay, editWeek, normalizeBookingTime, validateBookingWeek } from "./schedule-editor.utils";

describe("booking hours editing", () => {
  it.each([
    ["19", "19:00"],
    ["1", "01:00"],
    ["9:30", "09:30"],
    ["23:59", "23:59"],
    ["24", null],
    ["19:6", null],
    ["", null],
  ])("normalizes %s only when committed", (input, expected) => expect(normalizeBookingTime(input)).toBe(expected));
  it("copies all ranges to active days without enabling days off or sharing identities", () => {
    const week = editWeek({
      mon: [
        { start: "9", end: "12" },
        { start: "13", end: "19" },
      ],
      tue: [{ start: "10", end: "11" }],
    });
    const result = copyBookingDay(week, "mon", false);
    expect(result.tue.map(({ start, end }) => ({ start, end }))).toEqual([
      { start: "9", end: "12" },
      { start: "13", end: "19" },
    ]);
    expect(result.sun).toEqual([]);
    expect(result.tue[0].id).not.toBe(result.mon[0].id);
    expect(week.tue[0].start).toBe("10");
  });
  it("explicitly enables all days when requested", () => {
    const result = copyBookingDay(editWeek({ mon: [{ start: "9", end: "19" }] }), "mon", true);
    expect(Object.values(result).every((intervals) => intervals.length === 1)).toBe(true);
  });
  it("rejects overlaps and reversed ranges but permits adjacent ranges", () => {
    const week = editWeek({
      mon: [
        { start: "09:00", end: "12:00" },
        { start: "12:00", end: "19:00" },
      ],
    });
    expect(validateBookingWeek(week).valid).toBe(true);
    week.mon[1].start = "11";
    expect(validateBookingWeek(week).valid).toBe(false);
    week.mon[1].start = "20";
    expect(validateBookingWeek(week).valid).toBe(false);
  });
});
