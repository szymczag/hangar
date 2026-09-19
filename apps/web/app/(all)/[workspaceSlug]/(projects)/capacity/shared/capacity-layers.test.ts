/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import type { TCapacityInterval } from "@/services/capacity.service";
import {
  CAPACITY_INTERVAL_LAYERS,
  ONLY_TRAINING_LAYERS,
  formatLayerParam,
  intervalLabel,
  isOnlyTraining,
  parseLayerParam,
} from "./capacity-timeline.utils";

const training = (summary?: string | null): TCapacityInterval => ({
  start: "2026-10-15T09:00:00Z",
  end: "2026-10-15T13:00:00Z",
  kind: "google_training",
  summary,
});

describe("parseLayerParam", () => {
  it("treats an absent or empty parameter as no filter", () => {
    for (const value of [null, undefined, "", "   "]) {
      expect(parseLayerParam(value).size, String(value)).toBe(CAPACITY_INTERVAL_LAYERS.length);
    }
  });

  it("ignores names it does not recognize rather than showing a blank week", () => {
    // A URL somebody trimmed by hand should still render the ledger.
    expect(parseLayerParam("nonsense,alsonothing").size).toBe(CAPACITY_INTERVAL_LAYERS.length);
  });

  it("always keeps working hours, whatever the parameter says", () => {
    // They are the canvas the rest is drawn on; without them the bars float.
    expect(parseLayerParam("workshop").has("working")).toBe(true);
    expect(parseLayerParam("google_training").has("working")).toBe(true);
  });

  it("keeps only the layers named", () => {
    const layers = parseLayerParam("google_training");

    expect([...layers].toSorted()).toEqual(["google_training", "working"]);
  });
});

describe("formatLayerParam", () => {
  it("writes nothing when everything is shown, so the URL stays clean", () => {
    expect(formatLayerParam(new Set(CAPACITY_INTERVAL_LAYERS))).toBe("");
  });

  it("round-trips a narrowed selection", () => {
    const narrowed = new Set<TCapacityInterval["kind"]>(["working", "google_training", "workshop"]);

    expect([...parseLayerParam(formatLayerParam(narrowed))].toSorted()).toEqual(
      ["google_training", "working", "workshop"].toSorted()
    );
  });
});

describe("isOnlyTraining", () => {
  it("recognizes the shortcut and nothing else", () => {
    expect(isOnlyTraining(ONLY_TRAINING_LAYERS)).toBe(true);
    expect(isOnlyTraining(new Set(CAPACITY_INTERVAL_LAYERS))).toBe(false);
    expect(isOnlyTraining(new Set(["working", "google_training", "workshop"]))).toBe(false);
  });
});

describe("intervalLabel", () => {
  it("names the training when the viewer may read its title", () => {
    expect(intervalLabel(training("Network security"))).toBe("Training: Network security");
  });

  it("stays generic when there is no title to show", () => {
    // Either the viewer is not entitled to it, or the sweep has not recorded
    // one. Both look the same here on purpose.
    expect(intervalLabel(training(null))).toBe("Training invitation");
    expect(intervalLabel(training(undefined))).toBe("Training invitation");
    expect(intervalLabel(training(""))).toBe("Training invitation");
  });
});
