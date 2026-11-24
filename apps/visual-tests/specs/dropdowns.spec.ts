/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The property dropdowns on the work item create modal, open.
 *
 * The dropdowns moved to the `@plane/blocks` selects in phase 1b; since phase
 * 4c the modal is a Propel dialog that calls upstream's selects directly, so
 * the triggers are found by the test ids upstream gives them. The closed
 * triggers show in every work item baseline; the open panels showed nowhere
 * until these.
 *
 * One modal per story rather than one modal and four dropdowns: Escape closes
 * the dropdown, but the modal listens for it too, so the next dropdown would
 * open over a modal that may or may not have closed behind it.
 *
 * The calendar shows the month the seed's clock is in, and the fixtures freeze
 * the browser on that clock, so the day grid and the highlighted day are the
 * same on every run.
 */
async function openCreateModal(page: Page): Promise<Locator> {
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);
  await expect(page.getByText(seed.workItems[0], { exact: false }).first()).toBeVisible();

  // The power-k sequence for "Create work item".
  await page.keyboard.press("n");
  await page.keyboard.press("i");

  // Since phase 4c the dialog is Propel's: the Base UI popup carries role="dialog" and its size.
  const dialog = page.getByRole("dialog").filter({ has: page.getByPlaceholder("Title") });
  await settled(dialog);
  await expect(dialog.getByPlaceholder("Title")).toBeVisible();
  return dialog;
}

test("the state dropdown on the work item create modal", async ({ asUser }) => {
  const page = await asUser("light");
  const dialog = await openCreateModal(page);

  await dialog.getByTestId("create-work-item-state-select").click();
  // The last seeded state: once it is listed, the ones before it are too.
  const done = page.getByRole("option", { name: "Done" });

  await capture(page, "dropdowns-state", { ready: done });
});

test("the priority dropdown on the work item create modal", async ({ asUser }) => {
  const page = await asUser("light");
  const dialog = await openCreateModal(page);

  await dialog.getByTestId("create-work-item-priority-select").click();
  const low = page.getByRole("option", { name: "Low" });

  await capture(page, "dropdowns-priority", { ready: low });
});

test("the assignees dropdown on the work item create modal", async ({ asUser }) => {
  const page = await asUser("light");
  const dialog = await openCreateModal(page);

  await dialog.getByTestId("create-work-item-assignee-select").click();
  // Every project member is listed; the admin is seeded last.
  const admin = page.getByRole("option", { name: /VR Admin/ });

  await capture(page, "dropdowns-assignees", { ready: admin });
});

test("the start date picker on the work item create modal", async ({ asUser }) => {
  const page = await asUser("light");
  const dialog = await openCreateModal(page);

  await dialog.getByTestId("create-work-item-start-date-select").click();
  const calendar = page.getByRole("grid");

  await capture(page, "dropdowns-start-date", { ready: calendar });
});
