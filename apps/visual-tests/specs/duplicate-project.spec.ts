/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The duplicate-project modal, which is where this whole effort started.
 *
 * Its prefilled name -- "<project> (Copy)" -- was rejected by its own endpoint,
 * because the display name was being held to the identifier's character rule.
 * That was the first of the defects nobody's tests could see, so the prefill is
 * asserted here rather than merely photographed: a modal that rendered with an
 * undefined project would still look perfectly reasonable.
 *
 * Opened from project settings, where there is exactly one trigger. The button
 * reads "Duplicate" while the section title behind it reads "Duplicate
 * project", so the click has to be scoped or it matches both.
 */
test("the duplicate project modal", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/projects/${seed.project.id}`);

  // The Duplicate trigger is not gated on the project having loaded: the section
  // holding it renders as a sibling of the `currentProjectDetails ? Form :
  // Loader` ternary, gated only on being an admin. So the button is clickable
  // while the form above it is still a skeleton, and the prefill asserted below
  // is then racing the project fetch rather than reading a settled form.
  //
  // Not a backdrop problem, despite this modal sharing build-identity's 30%
  // backdrop: hiding the form and re-photographing the dialog leaves the image
  // byte-identical, so nothing behind this panel reaches the corners. Checked,
  // because assuming it did would have put a confident and false comment here.
  await expect(main.locator("#identifier")).toHaveValue(seed.project.identifier);

  const trigger = main.getByRole("button", { name: "Duplicate", exact: true });
  await expect(trigger).toBeVisible();
  await trigger.click();

  // The panel, not the wrapper: the element carrying role="dialog" is Headless
  // UI's outermost div, which has no size of its own and is never "visible".
  await expect(page.getByRole("dialog")).toHaveCount(1);
  const dialog = page.locator('[id^="headlessui-dialog-panel"]');
  await settled(dialog);

  const options = dialog.getByText("States and work item types are always copied.");
  await expect(options).toBeVisible();
  // The prefill that used to be refused by the endpoint behind this form.
  await expect(dialog.locator("#duplicate-project-name")).toHaveValue("Visual Regression (Copy)");

  await capture(page, "duplicate-project-modal", { ready: options, target: dialog });
});
