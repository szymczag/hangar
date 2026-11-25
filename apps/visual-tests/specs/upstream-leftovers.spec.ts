/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * Screens phase 9 moves to Propel that no story showed: the upstream files the
 * earlier phases left on `@plane/ui`, the in-repo `packages/propel`, Headless UI
 * or lucide (FORK.md ledger).
 *
 * - the project archives page, whose header and breadcrumbs move (the seed
 *   archives nothing, so it is the empty state);
 * - the create workspace page, whose form moves;
 * - the billing settings page, Hangar's one community edition card;
 * - a cycle's quick actions menu, whose items come from the shared factory.
 *
 * Every story is read-only: nothing is typed or submitted, and the menu is
 * opened and photographed, never used.
 */

test("the project archives page", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/archives/issues`);
  const empty = main.getByText("No archived work items yet", { exact: true }).first();

  await capture(page, "project-archives", { ready: empty, target: main });
});

test("the create workspace page", async ({ asUser }) => {
  const page = await asUser("light");

  await page.goto("/create-workspace");
  // The form, not the heading: the heading also heads the "creation disabled" branch's sibling.
  await capture(page, "create-workspace", { ready: page.locator("#workspaceUrl") });
});

test("workspace settings: billing", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/billing`);
  const card = main.getByText("Enjoy unlimited, free, community-based Hangar.", { exact: true }).first();

  await capture(page, "workspace-settings-billing", { ready: card, target: main });
});

test("a cycle's quick actions menu", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/cycles`);
  await expect(main.getByText(seed.cycles.draft.name, { exact: true }).first()).toBeVisible();
  // The draft cycle is the only row in the open "Upcoming" group.
  await main.getByRole("button", { name: "Options", exact: true }).first().click();
  const menu = page.getByRole("menu").last();

  await capture(page, "cycle-quick-actions", {
    ready: menu.getByRole("menuitem", { name: /Copy link/ }).first(),
    target: menu,
  });
});
