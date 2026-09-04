/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The shared quick links an admin sets for everyone, and the page they set them
 * on.
 *
 * The widget returns `null` when there are no links at all, and renders its
 * "show hidden" affordance only when the viewer has hidden one -- so the seed
 * provides two visible links and one hidden for the light user specifically.
 * A seed with three visible links would photograph a different component and
 * nobody would notice.
 */
test("shared quick links on the workspace home page", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/`);

  await Promise.all(seed.sharedLinks.visible.map((title) => expect(main.getByText(title).first()).toBeVisible()));
  // The hidden one must *not* be on the page; if it were, the seed's hide row
  // stopped working and the story would be photographing the wrong state.
  await expect(main.getByText(seed.sharedLinks.hidden[0])).toHaveCount(0);

  await capture(page, "workspace-home-shared-links", {
    ready: main.getByText(seed.sharedLinks.visible[0]).first(),
    target: main,
  });
});

test("the home defaults settings page", async ({ asUser }) => {
  // An ordinary member gets "you are not authorized" here, which is a stable
  // and completely uninformative thing to photograph.
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/home-defaults`);

  const description = main.getByText("What people see on their home page when they join this workspace.");
  await expect(description).toBeVisible();
  await expect(main.getByText(/not authorized/i)).toHaveCount(0);

  await capture(page, "workspace-home-defaults", { ready: description, target: main });
});
