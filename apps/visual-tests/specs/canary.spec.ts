/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test } from "@playwright/test";

/**
 * A page with no application in it at all.
 *
 * This is the most valuable story in the suite and it renders nothing anybody
 * ships. When thirty baselines fail at once the reviewer has to decide between
 * "the interface changed" and "the environment changed", and without evidence
 * the second is a plausible and fatal guess -- it leads to updating every
 * baseline and swallowing a real regression along the way.
 *
 * So: if this fails, it is the environment. If this passes and others fail, it
 * is the code. That is the whole job.
 *
 * It deliberately exercises what actually drifts between browser builds and
 * font stacks: glyph rasterisation at several sizes, a hairline that is prone
 * to rounding, and a blurred shadow.
 */
const CANARY = `<!doctype html>
<meta charset="utf-8">
<style>
  body { margin: 0; padding: 24px; background: #fff; font-family: Inter, system-ui, sans-serif; }
  .row { margin-bottom: 16px; color: #101010; }
  .s11 { font-size: 11px; } .s14 { font-size: 14px; } .s24 { font-size: 24px; font-weight: 600; }
  .hairline { height: 0; border-top: 1px solid #c8c8c8; margin: 20px 0; }
  .shadow { width: 160px; height: 64px; background: #fff; border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,.18); }
</style>
<div class="row s11">Hamburgefonstiv 0123456789</div>
<div class="row s14">Hamburgefonstiv 0123456789</div>
<div class="row s24">Hamburgefonstiv 0123456789</div>
<div class="hairline"></div>
<div class="shadow"></div>`;

test("the environment renders as it did when the baselines were taken", async ({ page }) => {
  await page.setContent(CANARY);
  await page.evaluate(() => document.fonts.ready);

  await expect(page.locator(".shadow")).toBeVisible();
  await expect(page).toHaveScreenshot("canary.png");
});
