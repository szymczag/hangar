/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The project pages list and its filters, a page in the editor with its
 * toolbar, the page export dialog, the stickies page, and the project view
 * list's filters, which share their created date and created by sections with
 * the pages filters.
 *
 * These move to Propel in phase 6 (FORK.md ledger). None of them showed in any
 * story before.
 *
 * The seed creates two public pages and one sticky for the light user. The
 * editor loads the first page's stored HTML through the live server, which is
 * how every page without collaborative state opens; nothing here types into it.
 * Live stores the page as it opens it, so the list is seeded with that page as
 * the most recently modified and reads the same in either order.
 * The export dialog is opened, never submitted.
 */

async function pagesList(page: Page): Promise<Locator> {
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/pages`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(seed.pages.names[0], { exact: true }).first()).toBeVisible();
  // Off the list, so the row does not play its hover state.
  await page.mouse.move(0, 0);
  return main;
}

async function pageEditor(page: Page): Promise<{ main: Locator; editor: Locator }> {
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/pages/${seed.pages.ids[0]}`);
  const main = page.getByRole("main").last();
  // The content arrives over the collaborative session, after the document.
  const editor = main.locator(".ProseMirror", { hasText: "The last paragraph." }).first();
  await expect(editor).toBeVisible();
  await page.mouse.move(0, 0);
  return { main, editor };
}

/** A dialog's panel: Headless UI's panel on 1.4 (its root has no box), the Base UI popup on Propel. */
function dialogPanel(page: Page): Locator {
  return page.locator('[id^="headlessui-dialog-panel"], [role="dialog"]:not([id^="headlessui-dialog"])').last();
}

/** The menu trigger: the 1.4 ellipsis menu, or Propel's icon button. */
function moreActions(page: Page): Locator {
  return page.locator('button[aria-label="More actions"], button:has(svg.lucide-ellipsis)');
}

test("the project pages list", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = await pagesList(page);

  await capture(page, "pages-list", {
    ready: main.getByText(seed.pages.names[1], { exact: true }).first(),
    target: main,
  });
});

test("the project pages filters", async ({ asUser }) => {
  const page = await asUser("light");
  const main = await pagesList(page);

  await main
    .getByRole("button", { name: /Filters/ })
    .first()
    .click();
  const createdBy = page.getByText(/^Created by/).last();
  await expect(createdBy).toBeVisible();

  await capture(page, "pages-list-filters", { ready: createdBy });
});

test("a page in the editor, with its toolbar", async ({ asUser }) => {
  const page = await asUser("light");
  const { main, editor } = await pageEditor(page);

  await capture(page, "page-editor", { ready: editor.getByText("Before the release"), target: main });
});

test("the page export dialog", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await pageEditor(page);

  // The page's own menu: the one in the header row that carries its name, not
  // the sidebar's or the editor's drag handles.
  const menu = moreActions(page);
  await page.locator("div").filter({ hasText: seed.pages.names[0] }).filter({ has: menu }).last().locator(menu).click();
  await page.getByRole("menuitem", { name: "Export" }).click();
  const dialog = dialogPanel(page);
  const exportButton = dialog.getByRole("button", { name: "Export", exact: true });
  await expect(exportButton).toBeVisible();

  await capture(page, "page-export-dialog", { ready: exportButton, target: dialog });
});

test("the stickies page", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/stickies`);
  const main = page.getByRole("main").last();
  const sticky = main.locator(".ProseMirror", { hasText: seed.sticky }).first();
  await expect(sticky).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "stickies", { ready: sticky, target: main });
});

test("the project view list filters", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  // Views are off on the seeded project; only the flag is patched, as in
  // views-and-drafts.spec.ts.
  await page.route(
    (url) => new RegExp(`/api/workspaces/[^/]+/projects/(details/|${seed.project.id}/)?$`).test(url.pathname),
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      const response = await route.fetch();
      const body: unknown = await response.json();
      const enable = (project: unknown): unknown =>
        project && typeof project === "object" && (project as { id?: unknown }).id === seed.project.id
          ? { ...project, issue_views_view: true }
          : project;
      await route.fulfill({ response, json: Array.isArray(body) ? body.map(enable) : enable(body) });
    }
  );
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/views`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(seed.views.project, { exact: true }).first()).toBeVisible();
  await page.mouse.move(0, 0);

  await page
    .getByRole("button", { name: /Filters/ })
    .first()
    .click();
  const createdBy = page.getByText(/^Created by/).last();
  await expect(createdBy).toBeVisible();

  await capture(page, "views-project-list-filters", { ready: createdBy });
});

/**
 * The callout's logo picker, which the editor draws with the shared emoji and
 * icon picker. Phase 9b moves it from the 1.4 picker to `@plane/blocks`.
 *
 * The page is the dark user's and private (see the seed), so opening it cannot
 * reorder the light user's pages list. The emoji grid only renders once the
 * picker has read its data from this instance's `emojibase` path, so waiting on
 * an emoji is also a check that the data is served locally rather than from a
 * CDN, which the Content-Security-Policy would refuse.
 */
test("the callout logo picker", async ({ asUser }) => {
  const page = await asUser("dark");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/pages/${seed.calloutPage.id}`);
  const main = page.getByRole("main").last();
  const callout = main.locator(".editor-callout-component", { hasText: seed.calloutPage.text }).first();
  await expect(callout).toBeVisible();

  // The picker's trigger is disabled until the collaborative session makes the
  // editor editable, and a click on it before then opens nothing.
  const logo = callout.getByRole("button").first();
  await expect(logo).toBeEnabled();
  await logo.click();
  const picker = page.getByRole("dialog").last();
  const emoji = picker.getByRole("button", { name: "grinning face", exact: true }).first();
  await expect(emoji).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "callout-logo-picker", { ready: emoji, target: picker });
});
