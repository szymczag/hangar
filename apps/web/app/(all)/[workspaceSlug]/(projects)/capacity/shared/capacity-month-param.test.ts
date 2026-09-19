/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { formatMonthParam, parseMonthParam, shiftMonth, startOfMonth } from "./capacity-format.utils";

// Built with the local `Date` constructor on purpose, the same way the week
// tests do: these values are local calendar months, and writing them as UTC
// literals would make the tests agree with the code only in one timezone.
const at = (year: number, month: number, day = 1) => new Date(year, month - 1, day, 12, 0, 0, 0);

describe("month window", () => {
  it("snaps to the first of the month at local midnight", () => {
    const start = startOfMonth(at(2026, 10, 17));

    expect(start.getFullYear()).toBe(2026);
    expect(start.getMonth()).toBe(9);
    expect(start.getDate()).toBe(1);
    expect(start.getHours()).toBe(0);
  });

  it("steps whole months without skipping short ones", () => {
    // The trap: stepping a month from the 31st lands on a day the next month
    // does not have, and rolls over. January would step to March.
    expect(formatMonthParam(shiftMonth(at(2026, 1, 31), 1))).toBe("2026-02");
    expect(formatMonthParam(shiftMonth(at(2026, 3, 31), -1))).toBe("2026-02");
  });

  it("steps across a year boundary in both directions", () => {
    expect(formatMonthParam(shiftMonth(at(2026, 12, 15), 1))).toBe("2027-01");
    expect(formatMonthParam(shiftMonth(at(2026, 1, 15), -1))).toBe("2025-12");
  });

  it("round-trips through the URL", () => {
    const start = startOfMonth(at(2026, 10, 17));

    expect(formatMonthParam(parseMonthParam(formatMonthParam(start), at(2020, 1)))).toBe("2026-10");
  });
});

describe("parseMonthParam", () => {
  const fallback = at(2026, 6, 15);

  it("falls back on anything malformed", () => {
    for (const value of [null, undefined, "", "2026", "2026-1", "2026-10-01", "not-a-month", "20xx-10"]) {
      expect(formatMonthParam(parseMonthParam(value, fallback)), String(value)).toBe("2026-06");
    }
  });

  it("rejects a month number that does not exist", () => {
    // `new Date(2026, 12, 1)` is January 2027, silently. A URL naming month 13
    // must not quietly show a different year.
    expect(formatMonthParam(parseMonthParam("2026-13", fallback))).toBe("2026-06");
    expect(formatMonthParam(parseMonthParam("2026-00", fallback))).toBe("2026-06");
  });

  it("accepts the edges of the year", () => {
    expect(formatMonthParam(parseMonthParam("2026-01", fallback))).toBe("2026-01");
    expect(formatMonthParam(parseMonthParam("2026-12", fallback))).toBe("2026-12");
  });

  it("never returns an invalid date", () => {
    for (const value of ["9999-12", "0001-01", "2026-13"]) {
      expect(Number.isNaN(parseMonthParam(value, fallback).getTime()), String(value)).toBe(false);
    }
  });
});
