/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * Workshop sessions on a work item.
 *
 * This is a layout defect's story. The editor used to live in the properties
 * sidebar -- `md:w-1/4` wide, with a fixed 120px label gutter -- rendering seven
 * stacked rows per session against `datetime-local` inputs the browser will not
 * shrink. Three sessions produced twenty-one rows, none of them legible, and no
 * check in CI could see it: types, lint and tests all passed on it.
 *
 * The seed carries three sessions rather than one for the same reason. One
 * session hid the problem; three are what made it obvious.
 */
test("workshop sessions in the work item", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues/${seed.workshop.id}`);

  const sessions = page.locator("#workshop-sessions");
  // The save button only exists once the schedule has loaded and rendered its
  // sessions, so it cannot be satisfied by the section's own heading.
  const ready = sessions.getByRole("button", { name: /Save schedule/i });
  await expect(ready).toBeVisible();
  await expect(sessions.getByText(/Session 3 of 3/)).toBeVisible();

  await capture(page, "workshop-sessions", { ready, target: sessions });
});

/**
 * The same sessions in the peek panel.
 *
 * Asserted, not photographed. This surface would not hold still at zero
 * tolerance: across CI runs it moved by roughly fourteen hundred pixels, and
 * within a single run the first attempt differed from both retries by another
 * fifty-five. The full-page story covers the same component and is stable, so
 * the pixels are not lost -- what this adds is the guarantee that the section
 * exists here at all, which is the defect it was written for: the editor used to
 * be mounted only by the full page, so a workshop opened from a board or a list
 * had no session UI whatsoever.
 *
 * The README's rule is that a story which cannot be made stable does not ship a
 * baseline, and raising the tolerance to keep one is how a visual suite turns
 * into noise. Left as an assertion until the instability is understood; the
 * candidate is the peek panel's own mount and transition, not the session
 * markup, since the same markup is stable one route away.
 */
test("workshop sessions in the peek panel", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues/`);
  const row = page.getByText(seed.workshop.name, { exact: true }).first();
  await expect(row).toBeVisible();
  await row.click();

  const sessions = page.locator("#workshop-sessions");
  await expect(sessions.getByRole("button", { name: /Save schedule/i })).toBeVisible();
  // The content, since there is no picture of it: three sessions, both trainers,
  // and the fields the sidebar could not fit.
  await expect(sessions.getByText(/Session 3 of 3/)).toBeVisible();
  await expect(sessions.getByText(seed.trainers[0], { exact: false }).first()).toBeVisible();
  await expect(sessions.getByLabel(/Session 1 starts/i)).toBeVisible();
});
