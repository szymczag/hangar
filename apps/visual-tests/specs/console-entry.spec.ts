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

/**
 * God Mode 0.3.0-rc.1 threw React error #418 on every load after the first:
 * its prerendered index.html had an empty body (the HydrateFallback loader was
 * gated on i18n), and with the chunks cached i18n was ready at hydration, so
 * the first client render did not match. The deterministic guard for that is
 * `apps/admin/tests/built-assets.build.test.mjs`, which checks the prerendered
 * loader; this story only reproduces the timing when the repeat load is served
 * from cache, which the VR edge does not promise (it sends no cache headers).
 * What it does hold is that neither load raises a page error. No screenshot.
 */
test("the console hydrates cleanly on a repeat load", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  const signIn = page.getByRole("button", { name: "Sign in" });
  await page.goto("/god-mode/");
  await expect(signIn).toBeVisible();
  await page.goto("/god-mode/");
  await expect(signIn).toBeVisible();

  expect(errors).toEqual([]);
});
