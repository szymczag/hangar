/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Page from "./page";

const state = vi.hoisted(() => ({ data: {} as Record<string, unknown> }));
vi.mock("swr", () => ({ default: () => ({ data: { results: [] }, mutate: async () => {} }), mutate: async () => {} }));
vi.mock("@/hooks/store/use-instance", () => ({
  useInstance: () => ({ config: { is_google_calendar_capacity_enabled: true } }),
}));
vi.mock("../shared/use-capacity-data", () => ({ useCapacityData: () => state.data }));
vi.mock("../shared/week-stepper", () => ({ WeekStepper: () => null }));
vi.mock("@plane/ui", () => ({ Spinner: () => <p>Loading</p> }));
vi.mock("@/components/core/page-title", () => ({ PageHead: () => null }));
vi.mock("@/components/auth-screens/not-authorized-view", () => ({ NotAuthorizedView: () => null }));
vi.mock("@plane/propel/button", () => ({
  Button: ({ children, disabled }: React.PropsWithChildren<{ disabled?: boolean }>) => (
    <button disabled={disabled}>{children}</button>
  ),
}));

const from = new Date(2099, 8, 7);
const to = new Date(2099, 8, 14);
const capacity = {
  from: from.toISOString(),
  to: to.toISOString(),
  trainers: [
    {
      trainer_id: "trainer",
      display_name: "Trainer",
      timezone: "Europe/Warsaw",
      availability_status: "fresh",
      intervals: [
        { start: new Date(2099, 8, 7, 9).toISOString(), end: new Date(2099, 8, 7, 12).toISOString(), kind: "working" },
      ],
    },
  ],
};
const render = () =>
  renderToStaticMarkup(<Page {...({ params: { workspaceSlug: "workspace" } } as Parameters<typeof Page>[0])} />);

beforeEach(() => {
  state.data = {
    capacity,
    capacityLoading: false,
    trainersLoading: false,
    weekStart: from,
    weekEnd: to,
    setWeekStart: vi.fn(),
    mutateTrainers: vi.fn(),
    refreshCapacity: vi.fn(),
  };
});

describe("planner availability states", () => {
  it("shows the required complete block and the longest actual opening", () => {
    const html = render();
    expect(html).toContain("6h 30m");
    expect(html).toContain("longest free opening is 3h");
    expect(html).toContain("Start another plan");
  });

  it("does not report no slots while previous-week data is retained", () => {
    state.data.weekStart = new Date(2099, 8, 14);
    state.data.weekEnd = new Date(2099, 8, 21);
    state.data.capacityLoading = true;
    const html = render();
    expect(html).toContain("Loading availability for this week");
    expect(html).not.toContain("No matching time this week");
    expect(html).not.toContain("Save plan &amp; hold");
  });

  it.each(["capacityError", "trainersError"])("distinguishes %s from an empty roster", (key) => {
    state.data.capacity = undefined;
    state.data[key] = new Error("Service unavailable");
    const html = render();
    expect(html).toContain("Availability could not be loaded");
    expect(html).toContain("Service unavailable");
    expect(html).not.toContain("No trainers to plan around");
  });

  it("waits for trainer loading before showing an empty roster", () => {
    state.data.capacity = undefined;
    state.data.trainersLoading = true;
    const html = render();
    expect(html).toContain("Loading");
    expect(html).not.toContain("No trainers to plan around");
  });
});
