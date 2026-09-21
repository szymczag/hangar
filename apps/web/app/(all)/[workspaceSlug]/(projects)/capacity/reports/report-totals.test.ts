/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import type { TTrainingReportRow } from "@/services/capacity.service";
import { rowTotal } from "./report-totals.utils";

const row = (overrides: Partial<TTrainingReportRow>): TTrainingReportRow => ({
  trainer_id: "trainer",
  display_name: "Trainer",
  sync_status: "ok",
  counts_towards_totals: true,
  workshop_count: 0,
  session_count: 0,
  delivery_minutes: 0,
  buffer_minutes: 0,
  external_confirmed_sessions: 0,
  external_confirmed_minutes: 0,
  external_pending_sessions: 0,
  external_pending_minutes: 0,
  ...overrides,
});

describe("rowTotal", () => {
  it("adds up the trainers it can vouch for", () => {
    const rows = [row({ trainer_id: "a", workshop_count: 3 }), row({ trainer_id: "b", workshop_count: 4 })];

    expect(rowTotal(rows, "workshop_count")).toBe(7);
  });

  it("leaves out a trainer whose calendar could not be read", () => {
    // The rule this function exists for. Folding an unreadable trainer in at
    // zero would read as "ran nothing" to somebody deciding who takes the next
    // workshop, which is the opposite of what the data says.
    const rows = [
      row({ trainer_id: "a", workshop_count: 3 }),
      row({ trainer_id: "b", workshop_count: 9, counts_towards_totals: false, sync_status: "never_synced" }),
    ];

    expect(rowTotal(rows, "workshop_count")).toBe(3);
  });

  it("totals nothing as zero rather than as not-a-number", () => {
    expect(rowTotal([], "delivery_minutes")).toBe(0);
    expect(rowTotal([row({ counts_towards_totals: false, delivery_minutes: 120 })], "delivery_minutes")).toBe(0);
  });
});
