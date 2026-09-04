/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, test } from "../src/fixtures.js";

/**
 * The two console screens reached without a session.
 *
 * Neither may call `asAdmin()`, and not merely because they are about being
 * signed out: that fixture puts the console cookie on the *shared* browser
 * context, so a page opened afterwards in the same test is authenticated too.
 * These live in their own file with their own contexts.
 *
 * The sign-in screen is also the one that proved the bundle guard was too
 * narrow. It was showing "Unable to fetch instance details" because the admin
 * bundle had been built against http://localhost:8000 -- `scripts/vr.mjs` only
 * inspected the web bundle, so nothing caught it. It checks both now.
 */
test("the console sign-in screen", async ({ page }) => {
  await page.goto("/god-mode/");

  const form = page.getByRole("button", { name: "Sign in" });
  await expect(form).toBeVisible();
  // The console renders this same shell when its instance fetch fails, so the
  // absence of that message is part of what makes the shot meaningful.
  await expect(page.getByText(/Unable to fetch/i)).toHaveCount(0);

  await capture(page, "console-sign-in", { ready: form });
});

test("the console not-found screen", async ({ page }) => {
  await page.goto("/god-mode/no-such-page");

  const message = page.getByText("Sorry, the page you are looking for cannot be found.");
  await capture(page, "console-not-found", { ready: message });
});
