/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { dayBounds, intervalLabel, intervalPosition } from "./capacity-timeline.utils";

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
});
