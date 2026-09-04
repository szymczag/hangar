/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, type Locator, type Page } from "@playwright/test";

/**
 * The only sanctioned way to take a screenshot in this suite.
 *
 * The readiness locator is mandatory, and that is the point. The translation
 * provider renders nothing until it has loaded its strings, and several surfaces
 * render nothing at all until their data arrives -- so a screenshot taken "when
 * the page has loaded" is frequently a screenshot of an empty box, which is
 * stable, pretty, and proves nothing forever.
 *
 * Waiting on the network is not an option either: the maintenance bar polls
 * every sixty seconds and the copy strip every three, so `networkidle` does not
 * merely under-deliver on those pages, it never fires.
 */
export async function capture(
  page: Page,
  name: string,
  options: {
    /** Something only present once the real content has rendered. */
    ready: Locator;
    /** Element to capture. Omit only for a deliberate full-viewport layout shot. */
    target?: Locator;
  }
): Promise<void> {
  // No timeout here on purpose. It is set once, for every assertion in the
  // suite, in playwright.config.ts. A local override is how this ended up
  // waiting 30s in some places and 60s in others, and the shorter number then
  // decided which stories failed under load.
  await expect(options.ready).toBeVisible();

  // Fonts settle after first paint, and a shot taken before they do captures a
  // fallback face that will never match the baseline.
  await page.evaluate(() => document.fonts.ready);

  // So do images, and for a while this waited only for fonts. CI caught what no
  // local run ever did: the build identity dialog's mark is an SVG <image>
  // loaded when the dialog opens, well after the navigation settled, and on a
  // cold runner the screenshot recorded an empty white square where the logo
  // goes -- a baseline identical to the real one in every other pixel.
  //
  // <img> exposes `complete`, so it can simply be waited on. SVG <image>
  // exposes nothing: no `complete`, no `naturalWidth`, and -- checked, not
  // assumed -- no entry in resource timing either, which is what a first
  // attempt at this wrongly relied on. Fetching each href is the available
  // signal that the bytes are resident; the request is served from cache when
  // the element has already loaded, and forces the load when it has not.
  await page.waitForFunction(() => Array.from(document.images).every((image) => image.complete));

  await page.evaluate(async () => {
    const hrefs = Array.from(document.querySelectorAll("image"))
      .map((element) => element.getAttribute("href") ?? element.getAttribute("xlink:href"))
      .filter((href): href is string => href !== null && !href.startsWith("data:"));

    await Promise.all(hrefs.map((href) => fetch(href, { cache: "force-cache" }).catch(() => undefined)));
  });

  const subject = options.target ?? page;
  await expect(subject).toHaveScreenshot(`${name}.png`);
}

/**
 * Wait for a headless-ui dialog to finish opening.
 *
 * `toBeVisible()` is satisfied at the *start* of a 300ms transition, so a
 * screenshot taken on it catches the panel mid-fade. Asserting the settled
 * values is a real assertion rather than a sleep, and it fails loudly if the
 * transition is ever changed.
 */
export async function settled(dialog: Locator): Promise<void> {
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveCSS("opacity", "1");
}

/**
 * Open an instance-console page and wait for it to be a page rather than a
 * skeleton.
 *
 * Every console page is `formattedConfig ? <Form/> : <Loader/>`, and the header
 * above that ternary renders immediately either way. So "the heading is
 * visible" is true while the body is still three grey rectangles -- which is
 * precisely how the first version of the god-mode story came to record the
 * console's *error* screen as its baseline.
 *
 * Two assertions, in this order. `ready` must be something only the loaded form
 * produces, and it is asserted first because it is the one that actually waits:
 * a page that has not rendered yet has no skeleton either, so the count check
 * alone would pass on an empty document. `<Loader>` carries `role="status"`
 * (packages/ui/src/loader.tsx), and nothing else in the console does.
 */
export async function consolePage(page: Page, path: string, ready: Locator): Promise<void> {
  await page.goto(path);
  await expect(ready).toBeVisible();
  await expect(page.getByRole("status")).toHaveCount(0);
}
