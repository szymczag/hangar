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
 * Worth its own baseline because for a long time this rendered nothing at all:
 * the editor was mounted only by the full page's sidebar, so a workshop opened
 * from a board or a list simply had no session UI.
 */
test("workshop sessions in the peek panel", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues/`);
  const row = page.getByText(seed.workshop.name, { exact: true }).first();
  await expect(row).toBeVisible();
  await row.click();

  const sessions = page.locator("#workshop-sessions");
  const ready = sessions.getByRole("button", { name: /Save schedule/i });
  await expect(ready).toBeVisible();

  await capture(page, "workshop-sessions-peek", { ready, target: sessions });
});
