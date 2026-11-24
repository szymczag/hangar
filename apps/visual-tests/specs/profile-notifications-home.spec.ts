/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * A user's profile, the notifications inbox and the home page widgets.
 *
 * These move to Propel in phase 7 (FORK.md ledger). The home page's shared
 * links already have a story in `workspace-home.spec.ts`; the profile and the
 * inbox showed in none.
 *
 * The seed adds two inbox notifications for the light user, both already
 * read: an unread one would add a badge to the sidebar in every story, and
 * opening it would mark it read, which the write guard refuses. The profile
 * needs nothing new: the light user's activity is the two worklog entries the
 * seed already logs, and the assigned work is the workshop.
 *
 * The home page's recents are served from the seed's manifest rather than the
 * live list. The server records a visit whenever a work item, a page or a
 * project is read, so the live list depends on which stories ran before this
 * one.
 */

/** A dialog's panel: Headless UI's panel on 1.4, the Base UI popup on Propel. */
function dialogPanel(page: Page): Locator {
  return page.locator('[id^="headlessui-dialog-panel"], [role="dialog"]:not([id^="headlessui-dialog"])').last();
}

/** Open the light user's own profile at `path` and return its main area. */
async function profilePage(page: Page, path: string): Promise<Locator> {
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/profile/${seed.users.light.id}/${path}`);
  return page.getByRole("main").last();
}

test("a user's profile overview", async ({ asUser }) => {
  const page = await asUser("light");
  const main = await profilePage(page, "");
  const heading = main.getByText("Work items by Priority", { exact: true }).first();
  await expect(heading).toBeVisible();
  await expect(main.getByText("Recent activity", { exact: true }).first()).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "profile-overview", { ready: heading, target: main });
});

test("a user's profile activity", async ({ asUser }) => {
  const page = await asUser("light");
  const main = await profilePage(page, "activity");
  const heading = main.getByText("Recent activity", { exact: true }).first();
  await expect(heading).toBeVisible();
  // The two worklog entries the seed logs, which are the light user's only
  // activity; the story must not photograph the list before they arrive.
  await expect(main.getByText(/VR Light/).first()).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "profile-activity", { ready: heading, target: main });
});

test("the notifications inbox", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/notifications/`);
  const main = page.getByRole("main").last();
  const card = main.getByText(seed.notifications.workItem).first();
  await expect(card).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "notifications-inbox", { ready: card, target: main });
});

test("the home page recents", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.route(
    (url) => new RegExp(`/api/workspaces/${seed.workspace.slug}/recent-visits/$`).test(url.pathname),
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      await route.fulfill({ json: seed.recents });
    }
  );
  await page.goto(`/${seed.workspace.slug}/`);
  const main = page.getByRole("main").last();
  // The seeded page, the second of the three rows.
  const row = main.getByText(seed.pages.names[0], { exact: true }).first();
  await expect(row).toBeVisible();
  await expect(main.getByText(seed.workshop.name, { exact: true }).first()).toBeVisible();
  await page.mouse.move(0, 0);

  await capture(page, "workspace-home-recents", { ready: row, target: main });
});

test("the home page's manage widgets dialog", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(seed.sharedLinks.visible[0]).first()).toBeVisible();

  await page
    .getByRole("button", { name: /Manage widgets/ })
    .first()
    .click();
  const dialog = dialogPanel(page);
  await settled(dialog);
  const recents = dialog.getByText("Recents", { exact: true }).first();

  await capture(page, "workspace-home-manage-widgets", { ready: recents, target: dialog });
});
