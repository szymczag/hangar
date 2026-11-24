/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The project's work item layouts, the filter and display menus above them,
 * and the create dialog.
 *
 * These move to Propel in phase 4b (FORK.md ledger). Until then a work item
 * list only showed up behind other stories (the dropdowns, the maintenance bar,
 * the command palette), and the board, spreadsheet, calendar and gantt layouts
 * nowhere.
 *
 * The layout is a per-user display preference the page reads from
 * `user-properties`. Switching it from the browser would save the preference,
 * which the write guard refuses, and the seed would need a second user per
 * layout. So only that preference is patched, on the real response: the work
 * items, states and properties are still the seeded round trip.
 *
 * The seeded work items carry no dates, so the calendar shows the month the
 * seed's clock is in without entries and the gantt chart lists the work items
 * without bars; both are still the frame the move restyles.
 */

type Layout = "list" | "kanban" | "spreadsheet" | "calendar" | "gantt_chart";

/** Serve the project's display preferences with `layout` (and what that layout needs). */
async function withLayout(page: Page, layout: Layout): Promise<void> {
  await page.route(
    (url) => /\/api\/workspaces\/[^/]+\/projects\/[^/]+\/user-properties\/$/.test(url.pathname),
    async (route) => {
      // A write goes on to the context's guard, which refuses and reports it.
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      const response = await route.fetch();
      const body = await response.json();
      body.display_filters = {
        ...body.display_filters,
        layout,
        // The board needs a grouping; the others take whatever is stored.
        ...(layout === "kanban" ? { group_by: "state", sub_group_by: null } : {}),
        ...(layout === "calendar" ? { calendar: { layout: "month", show_weekends: true } } : {}),
      };
      await route.fulfill({ response, json: body });
    }
  );
}

/** The project's work items page in `layout`, waited on until the first seeded work item shows. */
async function workItems(page: Page, layout: Layout): Promise<Locator> {
  const seed = fixtures();
  await withLayout(page, layout);
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);
  const main = page.getByRole("main").last();
  if (layout !== "calendar") await expect(main.getByText(seed.workItems[0], { exact: true }).first()).toBeVisible();
  // Off the layout, so no row or card under the pointer plays its hover state.
  await page.mouse.move(0, 0);
  return main;
}

test("the work item list layout", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await workItems(page, "list");

  await capture(page, "work-item-layout-list", {
    ready: main.getByText(seed.workItems[0], { exact: true }).first(),
    target: main,
  });
});

test("the work item board layout", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await workItems(page, "kanban");
  // The last seeded state's column, so every column before it has rendered.
  await expect(main.getByText("Done", { exact: true }).first()).toBeVisible();

  await capture(page, "work-item-layout-board", {
    ready: main.getByText(seed.workItems[0], { exact: true }).first(),
    target: main,
  });
});

test("the work item spreadsheet layout", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await workItems(page, "spreadsheet");

  await capture(page, "work-item-layout-spreadsheet", {
    ready: main.getByText(seed.workItems[0], { exact: true }).first(),
    target: main,
  });
});

test("the work item calendar layout", async ({ asUser }) => {
  const page = await asUser("light");
  const main = await workItems(page, "calendar");
  // The seed's clock is in January 2026, and the browser is frozen on it.
  const month = main.getByText(/January/).first();

  await capture(page, "work-item-layout-calendar", { ready: month, target: main });
});

test("the work item gantt layout", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await workItems(page, "gantt_chart");

  await capture(page, "work-item-layout-gantt", {
    ready: main.getByText(seed.workItems[0], { exact: true }).first(),
    target: main,
  });
});

test("the work item filters menu", async ({ asUser }) => {
  const page = await asUser("light");
  const main = await workItems(page, "list");

  // The add-filter trigger is icon-only (named only from v1.5.0 on); it sits
  // just before the "Display" menu in the header in both versions.
  const display = page.getByRole("button", { name: /Display/ }).first();
  await display.locator("xpath=preceding::button[1]").click();
  const priority = page.getByRole("option", { name: /Priority/ }).first();
  await expect(priority).toBeVisible();
  await expect(main).toBeVisible();

  await capture(page, "work-item-filters-menu", { ready: priority });
});

test("the work item display menu", async ({ asUser }) => {
  const page = await asUser("light");
  await workItems(page, "list");

  await page
    .getByRole("button", { name: /Display/ })
    .first()
    .click();
  const groupBy = page.getByText(/Group by/).first();

  await capture(page, "work-item-display-menu", { ready: groupBy });
});

test("the work item create dialog", async ({ asUser }) => {
  const page = await asUser("light");
  await workItems(page, "list");

  // The power-k sequence for "Create work item".
  await page.keyboard.press("n");
  await page.keyboard.press("i");

  // The panel, not the wrapper: Headless UI's role="dialog" element has no size of its own.
  const dialog = page.locator('[id^="headlessui-dialog-panel"]');
  await settled(dialog);
  const title = dialog.getByPlaceholder("Title");

  await capture(page, "work-item-create-dialog", { ready: title, target: dialog });
});
