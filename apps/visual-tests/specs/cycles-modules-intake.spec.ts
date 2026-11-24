/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * Cycles, modules, workspace analytics and intake.
 *
 * These move to Propel in phase 5 (FORK.md ledger). None of them showed in any
 * story before.
 *
 * The seed adds a completed cycle and a draft cycle, one module and one
 * pending intake work item. A completed cycle and a draft are the same on the
 * server's clock and on the browser's frozen one, whenever the suite runs; an
 * active cycle would not be. Neither cycle nor the module holds work items,
 * because the work item rows print their cycle and module and every layout
 * baseline would move.
 *
 * Intake is a project feature the seeded project leaves off, for the same
 * reason the views feature is: switching it on in the seed would add "Intake"
 * to the project's sidebar entry in every story. So the intake stories patch
 * only that flag on the real project responses.
 */

/** A dialog's panel: Headless UI's panel on 1.4, the Base UI popup on Propel. */
function dialogPanel(page: Page): Locator {
  return page.locator('[id^="headlessui-dialog-panel"], [role="dialog"]:not([id^="headlessui-dialog"])').last();
}

/** Serve the seeded project with its intake feature on. */
async function withIntakeFeature(page: Page): Promise<void> {
  const seed = fixtures();
  const enable = (project: unknown): unknown => {
    if (project && typeof project === "object" && (project as { id?: unknown }).id === seed.project.id) {
      return { ...project, inbox_view: true };
    }
    return project;
  };
  await page.route(
    (url) => new RegExp(`/api/workspaces/[^/]+/projects/(details/|${seed.project.id}/)?$`).test(url.pathname),
    async (route) => {
      // A write goes on to the context's guard, which refuses and reports it.
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      const response = await route.fetch();
      const body: unknown = await response.json();
      const json = Array.isArray(body) ? body.map(enable) : enable(body);
      await route.fulfill({ response, json });
    }
  );
}

/** Open a project page and wait until `text` shows in its main area. */
async function projectPage(page: Page, path: string, text: string): Promise<Locator> {
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/${path}`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(text, { exact: true }).first()).toBeVisible();
  // Off the content, so no row plays its hover state.
  await page.mouse.move(0, 0);
  return main;
}

test("the cycles list", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  // The draft cycle is listed under "Upcoming", which starts open; the
  // completed one is counted in the closed "Completed" group.
  const main = await projectPage(page, "cycles", seed.cycles.draft.name);

  await capture(page, "cycles-list", {
    ready: main.getByText(seed.cycles.draft.name, { exact: true }).first(),
    target: main,
  });
});

test("the cycles filters menu", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await projectPage(page, "cycles", seed.cycles.draft.name);

  await main
    .getByRole("button", { name: /Filters/ })
    .first()
    .click();
  // The status section's heading: a header row in the 1.4 popover, a submenu
  // row in upstream's menu, which keeps its options one level down.
  const status = page.getByText("Status of the cycle", { exact: true }).last();

  await capture(page, "cycles-filters-menu", { ready: status });
});

test("the cycle detail", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await projectPage(page, `cycles/${seed.cycles.completed.id}`, seed.cycles.completed.name);

  await capture(page, "cycle-detail", {
    ready: main.getByText(seed.cycles.completed.name, { exact: true }).first(),
    target: main,
  });
});

test("the modules list", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await projectPage(page, "modules", seed.module.name);

  await capture(page, "modules-list", {
    ready: main.getByText(seed.module.name, { exact: true }).first(),
    target: main,
  });
});

test("the module detail", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await projectPage(page, `modules/${seed.module.id}`, seed.module.name);

  await capture(page, "module-detail", {
    ready: main.getByText(seed.module.name, { exact: true }).first(),
    target: main,
  });
});

test("the workspace analytics overview", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/analytics/overview`);
  const main = page.getByRole("main").last();
  // The seeded project, listed among the active projects once the data is in.
  const project = main.getByText("Visual Regression", { exact: true }).first();
  await expect(project).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "analytics-overview", { ready: project, target: main });
});

test("the intake list and detail", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await withIntakeFeature(page);
  // The page opens the first open intake work item on its own; asking for it
  // in the address keeps the story off that redirect.
  const main = await projectPage(page, `intake?currentTab=open&inboxIssueId=${seed.intake.id}`, seed.intake.name);
  const decline = main.getByRole("button", { name: /Decline/ }).first();
  await expect(decline).toBeVisible();

  await capture(page, "intake-list-detail", { ready: decline, target: main });
});

test("the intake create dialog", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await withIntakeFeature(page);
  await projectPage(page, `intake?currentTab=open&inboxIssueId=${seed.intake.id}`, seed.intake.name);

  await page.getByRole("button", { name: "Add work item", exact: true }).first().click();
  const dialog = dialogPanel(page);
  await settled(dialog);
  const title = dialog.getByPlaceholder(/title/i).first();

  await capture(page, "intake-create-dialog", { ready: title, target: dialog });
});
