/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The instance console, which is a different application behind the same origin.
 *
 * The point of this story is the second cookie. `admin-session-id` and
 * `session-id` coexist because the session middleware picks the console cookie
 * for any path containing "instances" -- a substring rule that is easy to break
 * and impossible to notice from the application side. The seed mints a console
 * session already past its second factor, so WebAuthn is not a gate here.
 *
 * If the cookie handling regresses this lands on the console's sign-in screen,
 * which looks nothing like the baseline.
 */
test("the instance console", async ({ asAdmin }) => {
  const page = await asAdmin();
  fixtures();

  await page.goto("/god-mode/general");

  // Content only the General page can produce. The first version of this story
  // waited on "any level-3 heading", which the console's own "Unable to fetch
  // instance details" screen satisfies -- and it duly recorded that error page
  // as the baseline, stable and green and completely wrong. A readiness locator
  // has to be something the broken state cannot also render.
  const description = page.getByText("Identify your instances and get key details.");
  await expect(description).toBeVisible();
  await expect(page.getByText(/Unable to fetch/i)).toHaveCount(0);

  await capture(page, "god-mode-general", { ready: description });
});
