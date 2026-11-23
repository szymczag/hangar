/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The application shell's two popups, which the full-viewport maintenance
 * stories never open: the workspace switcher in the top navigation and the
 * command palette behind its search field. Both moved to Propel with the shell
 * (Base UI menu, cmdk list), so they get stories of their own.
 *
 * Both start from the work items page, not the workspace home: the home page
 * greets by time of day, which no baseline can hold.
 */
test("the workspace switcher in the top navigation", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);
  await expect(page.getByText(seed.workItems[0], { exact: false }).first()).toBeVisible();

  await page.getByRole("button", { name: "Open workspace switcher" }).click();
  const menu = page.locator("[data-workspace-switcher-menu]");
  // The last entry: once it is there, the workspace list above it has rendered.
  const signOut = menu.getByRole("menuitem", { name: "Sign out" });

  await capture(page, "shell-workspace-switcher", { ready: signOut, target: menu });
});

test("the command palette opened from the top navigation", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);
  await expect(page.getByText(seed.workItems[0], { exact: false }).first()).toBeVisible();

  await page.getByPlaceholder("Search commands...").click();
  const list = page.locator("[cmdk-list]");
  await expect(list.locator("[cmdk-item]").first()).toBeVisible();

  await capture(page, "shell-command-palette", { ready: list });
});
