/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The saved view lists and their create dialogs, in the project and in the
 * workspace, and the workspace drafts page.
 *
 * These move to Propel in phase 4c with the work item create dialog (FORK.md
 * ledger). None of them showed in any story before.
 *
 * The seed saves one public view in the project and one in the workspace, so
 * the lists show a row rather than their empty state. Views are a project
 * feature the seeded project leaves off: switching it on in the seed would add
 * "Views" to the project's sidebar entry in every story that shows the
 * sidebar. So, as the layout stories patch the layout preference, only the
 * feature flag is patched on the real project responses, and only here.
 *
 * The seed has no drafts, so the drafts page shows its empty state, which is
 * the frame the move restyles.
 */

/** A dialog's panel: Headless UI's panel on 1.4, the Base UI popup on Propel. */
function dialogPanel(page: Page): Locator {
  return page.locator('[id^="headlessui-dialog-panel"], [role="dialog"]:not([id^="headlessui-dialog"])').last();
}

/** Serve the seeded project with its views feature on. */
async function withViewsFeature(page: Page): Promise<void> {
  const seed = fixtures();
  const enable = (project: unknown): unknown => {
    if (project && typeof project === "object" && (project as { id?: unknown }).id === seed.project.id) {
      return { ...project, issue_views_view: true };
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

async function projectViews(page: Page): Promise<Locator> {
  const seed = fixtures();
  await withViewsFeature(page);
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/views`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(seed.views.project, { exact: true }).first()).toBeVisible();
  // Off the list, so the row does not play its hover state.
  await page.mouse.move(0, 0);
  return main;
}

async function workspaceViews(page: Page): Promise<Locator> {
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/workspace-views`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(seed.views.workspace, { exact: true }).first()).toBeVisible();
  await page.mouse.move(0, 0);
  return main;
}

test("the project views list", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await projectViews(page);

  await capture(page, "views-project-list", {
    ready: main.getByText(seed.views.project, { exact: true }).first(),
    target: main,
  });
});

test("the project view create dialog", async ({ asUser }) => {
  const page = await asUser("light");
  await projectViews(page);

  await page.getByRole("button", { name: "Add view", exact: true }).first().click();
  const dialog = dialogPanel(page);
  await settled(dialog);
  const title = dialog.getByPlaceholder(/title/i).first();

  await capture(page, "views-project-create-dialog", { ready: title, target: dialog });
});

test("the workspace views list", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await workspaceViews(page);

  await capture(page, "views-workspace-list", {
    ready: main.getByText(seed.views.workspace, { exact: true }).first(),
    target: main,
  });
});

test("the workspace view create dialog", async ({ asUser }) => {
  const page = await asUser("light");
  await workspaceViews(page);

  await page.getByRole("button", { name: "Add view", exact: true }).first().click();
  const dialog = dialogPanel(page);
  await settled(dialog);
  const title = dialog.getByPlaceholder(/title/i).first();

  await capture(page, "views-workspace-create-dialog", { ready: title, target: dialog });
});

test("the workspace drafts page", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/drafts`);
  const main = page.getByRole("main").last();
  const title = main.getByText("Half-written work items", { exact: true });
  await expect(title).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "drafts-empty", { ready: title, target: main });
});
