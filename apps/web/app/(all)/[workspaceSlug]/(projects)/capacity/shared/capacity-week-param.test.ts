/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { formatWeekParam, parseWeekParam, startOfWeek } from "./capacity-format.utils";

describe("the ?week= parameter", () => {
  it("round-trips the week it was given", () => {
    const monday = startOfWeek(new Date(2026, 8, 9)); // Wednesday 9 September 2026
    expect(formatWeekParam(monday)).toBe("2026-09-07");
    expect(parseWeekParam("2026-09-07", new Date()).getTime()).toBe(monday.getTime());
  });

  it("writes the local calendar date, not the UTC one", () => {
    // A Monday local midnight in any timezone east of Greenwich is the *Sunday*
    // in UTC. Serialising with toISOString() would name 06 September here, and
    // reading that back would walk the view a week earlier on every reload.
    const monday = new Date(2026, 8, 7, 0, 0, 0, 0);
    expect(formatWeekParam(monday)).toBe("2026-09-07");
    if (monday.getTimezoneOffset() < 0) {
      expect(monday.toISOString().slice(0, 10)).toBe("2026-09-06");
    }
  });

  it("snaps any day inside a week to that week's Monday", () => {
    // Two links naming the same week have to compose the same SWR key, or each
    // pays for its own request.
    const fromSunday = parseWeekParam("2026-09-13", new Date());
    const fromMonday = parseWeekParam("2026-09-07", new Date());
    expect(fromSunday.getTime()).toBe(fromMonday.getTime());
    expect(formatWeekParam(fromSunday)).toBe("2026-09-07");
  });

  it("falls back to the fallback week when the value is missing or malformed", () => {
    const fallback = new Date(2026, 8, 9);
    const expected = startOfWeek(fallback).getTime();
    for (const value of [null, undefined, "", "garbage", "2026-9-7", "07-09-2026", "2026-09-07T00:00:00Z"]) {
      expect(parseWeekParam(value, fallback).getTime()).toBe(expected);
    }
  });

  it("rejects a well-shaped date that does not exist", () => {
    // new Date(2026, 12, 40) rolls over into the following year rather than
    // throwing, so a plain constructor check would accept this.
    const fallback = new Date(2026, 8, 9);
    expect(parseWeekParam("2026-13-40", fallback).getTime()).toBe(startOfWeek(fallback).getTime());
    expect(parseWeekParam("2026-02-30", fallback).getTime()).toBe(startOfWeek(fallback).getTime());
  });

  it("never returns an invalid date", () => {
    for (const value of ["garbage", "9999-99-99", null]) {
      expect(Number.isNaN(parseWeekParam(value, new Date()).getTime())).toBe(false);
    }
  });
});
