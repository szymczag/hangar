/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The Todoist import history.
 *
 * Two things have to be true before this renders anything at all, and only one
 * of them is a database row. The screen is gated on
 * `config.is_todoist_imports_enabled`, which comes from the `TODOIST_IMPORTS_ENABLED`
 * process environment rather than from instance configuration -- so the compose
 * file sets it, and no amount of seeding would have been enough.
 *
 * The seeded jobs are deliberately both terminal. An active one makes this
 * component poll every three seconds and render a spinning loader; finished rows
 * give a static DOM and still show everything worth photographing -- the status
 * icons, the task tallies, the retry action on a failure, the report link on
 * both.
 */
test("the workspace import history", async ({ asUser }) => {
  // Admin: the screen refuses an ordinary member outright.
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/imports`);

  // The report link exists only for a job that actually finished. The "Recent
  // imports" heading would have been the obvious choice and is the wrong one:
  // it renders in the loading, empty and error states too.
  const report = main.getByRole("link", { name: /download report/i }).first();
  await expect(report).toBeVisible();
  await expect(main.getByText(/Completed · 128 of 128 tasks/)).toBeVisible();
  await expect(main.getByText(/Failed · 41 of 64/)).toBeVisible();

  // The history section, not the whole page. `main` here is taller than the
  // viewport, so a page-scoped shot clipped the failed row off the bottom --
  // photographing one and a half of the two rows the story asserts. Scoping
  // also leaves the upload wizard out, which is a different surface with a file
  // input in it.
  const history = main.getByRole("heading", { name: "Recent imports" }).locator("xpath=../..");
  await capture(page, "workspace-imports", { ready: report, target: history });
});
