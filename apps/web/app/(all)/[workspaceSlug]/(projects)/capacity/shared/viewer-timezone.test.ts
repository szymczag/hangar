/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */
import { expect, it } from "vitest";
import { parseWeekParam, shiftWeek, formatWeekParam } from "./capacity-format.utils";
import { dayBounds } from "./capacity-timeline.utils";

it.each([
  ["2026-03-23", 167, 23],
  ["2026-10-19", 169, 25],
])("keeps calendar boundaries across DST: %s", (date, hours, sundayHours) => {
  const start = parseWeekParam(date, new Date(), "Europe/Warsaw");
  expect(formatWeekParam(start)).toBe(date);
  expect((shiftWeek(start, 1).getTime() - start.getTime()) / 3_600_000).toBe(hours);
  const sunday = dayBounds(start, 6);
  expect((sunday.end.getTime() - sunday.start.getTime()) / 3_600_000).toBe(sundayHours);
});
