/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * Custom work item types and their properties.
 *
 * Renders nothing without seeded data -- the page shows an empty-list state
 * when a project has no types with active properties -- so a seed that stopped
 * producing them fails here rather than recording an empty panel. The seed
 * attaches one property of every kind the interface can render, because the
 * property widget is a switch on `property_type` and a baseline exercising only
 * text would say nothing about the other six.
 *
 * The matching story for the work item *sidebar* is deliberately absent, and
 * this is the note for whoever adds it. The panel is an `overflow-y-auto`
 * column whose height depends on the description editor settling beside it, and
 * capturing it produced a stable four pixels of difference along its right edge
 * on roughly one run in five -- a scrollbar arriving or not. Scoping the
 * capture to the panel took it from forty pixels to four; a taller viewport did
 * not remove the last four. It is not shipped rather than shipped flaky,
 * because a story that fails one run in five teaches people to ignore red, and
 * raising the tolerance to hide it would defeat the entire suite.
 */
test("the work item types settings page", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/projects/${seed.project.id}/work-item-types`);
  await expect(main.getByText("Organize work with Task, Epic, and custom types.")).toBeVisible();

  await capture(page, "work-item-types-settings", {
    ready: main.getByText(seed.properties[0]).first(),
    target: main,
  });
});
