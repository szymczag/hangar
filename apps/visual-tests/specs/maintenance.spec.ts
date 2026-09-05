/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The maintenance bar, captured full-viewport on purpose.
 *
 * This is the whole-page story: the bar plus the shell it displaces, at two
 * widths, so that anything which moves the application's bottom edge or squeezes
 * the sidebar shows up. It is not element-scoped like its neighbours because the
 * point is the relationship between the bar and everything under it.
 *
 * One correction to the note this story was written from. It claimed to guard
 * the change of `<main>` from `h-full` to `min-h-0 flex-1`, on the grounds that
 * `h-full` pushes the page's bottom edge past the viewport once the bar takes a
 * sibling slot. Reverting that by hand and re-running proves otherwise: `<main>`
 * is a flex item with the default `flex-shrink: 1`, so `h-full` resolves to the
 * full container height and then shrinks to the space the bar leaves, exactly as
 * `flex-1` does. All three spellings render identically here, and this story
 * passes against every one of them. Whatever `min-h-0` is doing for the nested
 * scroll containers, it is not visible at this viewport with this content.
 *
 * What the story is verified to catch is a real change to the bar or the shell:
 * growing the bar's icon by four pixels fails all three maintenance stories, on
 * every retry.
 *
 * It also renders nothing at all unless the seed produced an active notice, so a
 * silently broken seed fails here rather than quietly recording an empty
 * baseline. And the list is deliberately longer than the viewport -- with a list
 * that fits, the content area is identical no matter what `<main>` does.
 */
for (const [name, width] of [
  ["wide", 1440],
  // 800, not 768: `sidebar-wrapper.tsx` collapses the entire sidebar at
  // `windowSize[0] < 768`, so 768 is calibrated one pixel from a completely
  // different layout. The story wants a narrow viewport, not a cliff edge.
  ["narrow", 800],
] as const) {
  test(`the maintenance bar does not clip the page (${name})`, async ({ asUser }) => {
    const page = await asUser("light");
    await page.setViewportSize({ width, height: 900 });
    const seed = fixtures();

    await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);

    const bar = page.getByRole("status").filter({ hasText: /Maintenance/ });
    // Just visible. An earlier version called `settled()` here with a comment
    // claiming the bar fades in under framer-motion -- there is no framer-motion
    // anywhere in this chain, `Banner` is a plain div, and its computed opacity
    // is 1 on the first painted frame. The call was satisfied instantly and
    // guarded nothing, which is worse than no guard because it reads like one.
    await expect(bar).toBeVisible();

    // The bar arrives long before the work items do, so waiting on it alone
    // captures a blank content pane -- stable today, and different the moment
    // the list happens to win the race. Wait for seeded content instead.
    await expect(page.getByText(seed.workItems.at(-1)!, { exact: false }).first()).toBeVisible();

    // And wait for the sidebar separately, because nothing about the work items
    // implies it has finished. Its personal entries are rendered from
    // preferences that arrive item by item, and the list re-sorts as each one
    // lands -- so a screenshot taken partway through catches a real but
    // transient order. Their sort_order values are distinct, so once all three
    // are present the order is fixed.
    // Scoped to the main sidebar: the same links exist in the peek view, which
    // is present in the DOM whether or not it is on screen.
    const sidebar = page.getByLabel("Main sidebar");
    await Promise.all(
      ["Drafts", "Your work", "Stickies"].map((entry) =>
        expect(sidebar.getByRole("link", { name: entry })).toBeVisible()
      )
    );

    await capture(page, `maintenance-bar-${name}`, {
      ready: page.getByText(seed.workItems[0], { exact: false }).first(),
    });
  });
}

test("the maintenance bar in dark", async ({ asUser }) => {
  const page = await asUser("dark");
  const seed = fixtures();
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);

  const bar = page.getByRole("status").filter({ hasText: /Maintenance/ });
  await expect(bar).toBeVisible();

  // Wait for the page behind it as well, even though only the bar is captured.
  // The route progress indicator is a thin line pinned to the very top of the
  // viewport, which overlaps the bar's top edge -- so a shot taken while the
  // navigation is still running differs from one taken after it by a single row
  // of pixels, and nothing about the bar itself says which it will be.
  await expect(page.getByText(seed.workItems[0], { exact: false }).first()).toBeVisible();

  await capture(page, "maintenance-bar-dark", { ready: bar, target: bar });
});
