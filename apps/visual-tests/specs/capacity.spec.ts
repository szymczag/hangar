/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The three surfaces `/capacity` was split into.
 *
 * They were one page of 963 lines holding a trainer's own settings, a
 * workspace-wide booking ledger, and the workshop planner. Nothing photographed
 * any of it, which is why the split was verified by hand at every step -- and
 * why the personal page's empty state, the one a colleague who is not yet a
 * trainer sees, was rebuilt from scratch after the ledger that used to carry it
 * moved away.
 *
 * All three are gated on `ENABLE_GOOGLE_CALENDAR_CAPACITY`, which this stack now
 * sets. Without it the seed's trainer profiles never exist, the Workshop work
 * item type is never provisioned, and these stories would photograph "not
 * authorized" three times over.
 */
test("my own capacity", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/capacity`);

  // Seeded booking hours, not a heading: the heading renders before the profile
  // arrives, and this page's whole content is that profile.
  const hours = main.getByText(/Booking hours/i).first();
  await expect(hours).toBeVisible();
  // The ledger and the planner must not be here. This is the assertion the
  // cutover actually turns on, and a presence-only check would pass without it.
  await expect(main.getByText(/Find a trainer and time/i)).toHaveCount(0);
  await expect(main.getByText(/What needs to happen/i)).toHaveCount(0);

  await capture(page, "capacity-personal", { ready: hours, target: main });
});

test("the personal capacity page before opting in", async ({ asUser }) => {
  // The admin persona is deliberately not a seeded trainer, so this is the
  // empty state rather than a contrivance.
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/capacity`);

  const optIn = main.getByRole("button", { name: /Become a trainer|Reactivate trainer/ });
  await expect(optIn).toBeVisible();

  await capture(page, "capacity-personal-empty", { ready: optIn, target: main });
});

test("team capacity", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/capacity/team`);

  // A seeded trainer's name, so the shot cannot be of an empty ledger.
  // The ledger renders both a mobile card list (`lg:hidden`) and a desktop grid,
  // so the trainer's name exists twice in the DOM and the first match is the
  // hidden one. Wait on the copy that is actually on screen.
  const trainer = main.getByText(seed.trainers[0], { exact: false }).filter({ visible: true }).first();
  await expect(main.getByText(/Find a trainer and time/i).first()).toBeVisible();
  await expect(trainer).toBeVisible();

  await capture(page, "capacity-team", { ready: trainer, target: main });
});

test("the workshop planner", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/capacity/planner`);

  // Candidates are computed from the capacity response, so waiting on one waits
  // on the fetch, the maths and the render together. "Matching slots" is just
  // the heading and renders with an empty list.
  const candidate = main.getByRole("button", { name: /hold for 72h/i }).first();
  await expect(candidate).toBeVisible();
  await expect(main.getByRole("button", { name: /Find first available/i })).toBeVisible();

  await capture(page, "capacity-planner", { ready: candidate, target: main });
});

test("planner explains a short opening and keeps earlier holds while planning more", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const trainerId = "10000000-0000-4000-8000-000000000001";
  const drafts: Array<{
    id: string;
    revision: number;
    title: string;
    duration_minutes: number;
    preparation_minutes: number;
    travel_before_minutes: number;
    travel_after_minutes: number;
    trainer_ids: string[];
    issue_id: null;
    issue: null;
    hold: null | {
      id: string;
      trainer_id: string;
      trainer_name: string;
      workshop_starts_at: string;
      workshop_ends_at: string;
      blocked_starts_at: string;
      blocked_ends_at: string;
      expires_at: string;
      status: "active";
    };
  }> = [];
  let capacityReads = 0;
  // Request-local fixtures exercise the real UI without changing the shared seed.
  await page.route("**/api/workspaces/*/capacity/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.split("/capacity/")[1];
    if (path === "trainers/") {
      await route.fulfill({
        json: {
          results: [{ id: trainerId, user_id: trainerId, display_name: "Planning trainer", status: "active" }],
          next_cursor: null,
        },
      });
    } else if (path === "") {
      capacityReads++;
      const start = new Date(url.searchParams.get("from")!);
      const end = new Date(url.searchParams.get("to")!);
      const intervals: Array<{ start: string; end: string; kind: string }> = [];
      const day = new Date(start);
      day.setUTCHours(0, 0, 0, 0);
      while (day.getTime() < end.getTime()) {
        if (day.getUTCDay() !== 0 && day.getUTCDay() !== 6) {
          const a = new Date(day);
          a.setUTCHours(9);
          const b = new Date(day);
          b.setUTCHours(12);
          intervals.push({ start: a.toISOString(), end: b.toISOString(), kind: "working" });
        }
        day.setUTCDate(day.getUTCDate() + 1);
      }
      for (const draft of drafts)
        if (draft.hold)
          intervals.push({
            start: draft.hold.blocked_starts_at,
            end: draft.hold.blocked_ends_at,
            kind: "workshop_hold",
          });
      await route.fulfill({
        json: {
          from: start.toISOString(),
          to: end.toISOString(),
          trainers: [
            {
              trainer_id: trainerId,
              display_name: "Planning trainer",
              timezone: "UTC",
              availability_status: "fresh",
              intervals,
            },
          ],
        },
      });
    } else if (path === "plans/") {
      if (request.method() === "GET") await route.fulfill({ json: { results: drafts } });
      else {
        const draft = {
          ...request.postDataJSON(),
          id: `plan-${drafts.length + 1}`,
          revision: 1,
          issue: null,
          hold: null,
        };
        drafts.push(draft);
        await route.fulfill({ status: 201, json: draft });
      }
    } else if (path.startsWith("plans/")) {
      const draft = drafts.find((item) => item.id === path.split("/")[1])!;
      if (path.endsWith("/hold/")) {
        if (request.method() === "POST") {
          const input = request.postDataJSON();
          expect(input.revision).toBe(draft.revision);
          const start = new Date(input.workshop_starts_at).getTime();
          const end = start + draft.duration_minutes * 60_000;
          draft.hold = {
            id: `hold-${draft.id}`,
            trainer_id: trainerId,
            trainer_name: "Planning trainer",
            status: "active",
            workshop_starts_at: new Date(start).toISOString(),
            workshop_ends_at: new Date(end).toISOString(),
            blocked_starts_at: new Date(
              start - (draft.preparation_minutes + draft.travel_before_minutes) * 60_000
            ).toISOString(),
            blocked_ends_at: new Date(end + draft.travel_after_minutes * 60_000).toISOString(),
            expires_at: new Date(new Date(seed.clock).getTime() + 72 * 3_600_000).toISOString(),
          };
        } else draft.hold = null;
        draft.revision++;
        await route.fulfill({ json: { revision: draft.revision, hold: draft.hold } });
      } else {
        throw new Error(`Unexpected plan operation: ${request.method()} ${path}`);
      }
    } else await route.fallback();
  });
  await page.goto(`/${seed.workspace.slug}/capacity/planner`);
  await expect(page.getByText("No matching time this week")).toBeVisible();
  await expect(page.getByText(/This plan needs 6h 30m/)).toBeVisible();
  await expect(page.getByText(/longest free opening is 3h/)).toBeVisible();

  await page.getByRole("button", { name: "Find first available" }).click();
  await expect(page.getByText(/No matching time found up to/)).toBeVisible();
  await page.getByRole("spinbutton", { name: /Workshop duration/ }).fill("30");
  await expect(page.getByText(/No matching time found up to/)).toHaveCount(0);
  await page.getByRole("button", { name: "Save plan & hold for 72h" }).first().click();
  await expect(page.getByText("Time held for Planning trainer")).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("planner-held.png"), fullPage: true });
  expect(drafts).toHaveLength(1);
  expect(drafts[0].duration_minutes).toBe(30);
  expect(drafts[0].title).not.toBe("");
  await expect(page.getByRole("spinbutton", { name: /Workshop duration/ })).toBeDisabled();

  await page.getByRole("button", { name: "Start another plan" }).click();
  // The first hold occupies the only remaining opening this week.
  await page.getByRole("button", { name: "Next week" }).click();
  await page.getByRole("spinbutton", { name: /Workshop duration/ }).fill("30");
  await page.getByRole("button", { name: "Save plan & hold for 72h" }).first().click();
  await expect(page.getByText("Time held for Planning trainer")).toBeVisible();
  expect(drafts).toHaveLength(2);
  expect(drafts.every((draft) => draft.hold !== null)).toBe(true);
  expect(drafts[0].hold!.workshop_starts_at).not.toBe(drafts[1].hold!.workshop_starts_at);

  await page.getByRole("combobox", { name: "Saved planning drafts" }).selectOption(drafts[0].id);
  const readsBeforeRelease = capacityReads;
  await page.getByRole("button", { name: "Release and edit" }).click();
  await expect(page.getByRole("spinbutton", { name: /Workshop duration/ })).toBeEnabled();
  await expect.poll(() => capacityReads).toBeGreaterThan(readsBeforeRelease);
  expect(drafts[0].hold).toBeNull();
  expect(drafts[1].hold).not.toBeNull();
});
