/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { test } from "../src/fixtures.js";

/**
 * The one surface with no session, and the only one where the browser's colour
 * scheme decides the theme: with no profile to read, next-themes resolves
 * `system` from `prefers-color-scheme`. Everywhere else the theme comes from
 * the signed-in user's stored profile.
 *
 * It also exercises the coldest path in the suite — first paint, font loading,
 * and the instance configuration fetch — which is why it is worth a baseline
 * even though nothing about it has ever been reported as wrong.
 */
test("the sign-in page", async ({ page }) => {
  await page.goto("/");
  await capture(page, "sign-in", {
    ready: page.getByRole("button", { name: /continue|sign in/i }).first(),
  });
});
