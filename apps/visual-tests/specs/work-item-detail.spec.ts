/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The work item detail page, its properties sidebar, its activity feed and the
 * peek overview.
 *
 * These move to Propel in phase 4a (FORK.md ledger). Before that only the
 * workshop sessions widget had a baseline, so each surface the move restyles
 * gets one here, photographed on the first seeded work item: it carries the
 * Task type's custom properties, two worklogs and a comment.
 *
 * The page stories sign in as the project admin, who also sees the worklog
 * controls (S20); the peek signs in as a member, like the workshop peek.
 *
 * Every story is read-only: nothing is typed or submitted, so the write guard
 * stays quiet.
 */

/** The admin's view of the first work item, waited on until its comment and worklogs have loaded. */
async function workItemPage(page: Page): Promise<Locator> {
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/browse/${seed.project.identifier}-1`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(seed.comment, { exact: true }).first()).toBeVisible();
  // The feed's worklog entry ("logged 1h 30m") and the sidebar's time tracking
  // total load separately from the comment (S20: both only for project members).
  await expect(main.getByText("1h 30m", { exact: true }).first()).toBeVisible();
  await expect(main.getByText("2h 15m", { exact: true }).first()).toBeVisible();
  return main;
}

test("the work item detail page", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = await workItemPage(page);

  await capture(page, "work-item-detail", {
    ready: main.getByText(seed.comment, { exact: true }).first(),
    target: main,
  });
});

test("the work item sidebar properties", async ({ asUser }) => {
  const page = await asUser("admin");
  const main = await workItemPage(page);

  // The properties column scrolls on its own; both the 1.4 and the Propel
  // sidebar put the "Properties" heading inside that scroller.
  const heading = main.getByText("Properties", { exact: true }).first();
  const sidebar = heading.locator(
    "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' overflow-y-auto ')][1]"
  );

  await capture(page, "work-item-sidebar", { ready: heading, target: sidebar });
});

test("the work item activity and comments", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = await workItemPage(page);

  // The feed's own block: the nearest ancestor of the comment that also holds
  // the "Activity" heading (1.4) or tab (Propel).
  const comment = main.getByText(seed.comment, { exact: true }).first();
  const activity = comment.locator("xpath=ancestor::div[.//*[normalize-space(text())='Activity']][1]");

  await capture(page, "work-item-activity", { ready: comment, target: activity });
});

test("the work item peek overview", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues/`);
  const row = page.getByText(seed.workItems[0], { exact: true }).first();
  await expect(row).toBeVisible();
  await row.click();
  // Off the panel, so no button under the pointer plays its hover transition
  // (see the workshop peek story).
  await page.mouse.move(0, 0);

  const peek = page.locator("#full-screen-portal [class*='md:w-[50%]']").first();
  const comment = peek.getByText(seed.comment, { exact: true }).first();
  await expect(comment).toBeVisible();
  await expect(peek.getByText("1h 30m", { exact: true }).first()).toBeVisible();
  await expect(peek.getByText("2h 15m", { exact: true }).first()).toBeVisible();

  await capture(page, "work-item-peek", { ready: comment, target: peek });
});
