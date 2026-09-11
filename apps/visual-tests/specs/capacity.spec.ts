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
  const candidate = main.getByRole("button", { name: /Hold for 72h/ }).first();
  await expect(candidate).toBeVisible();
  await expect(main.getByRole("button", { name: /Find first available/i })).toBeVisible();

  await capture(page, "capacity-planner", { ready: candidate, target: main });
});
