/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture, consolePage } from "../src/capture.js";
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

  // Third readiness locator for this one story, and the first that is actually
  // about the page. It waited on "any level-3 heading" (satisfied by the
  // console's own error screen, which it duly photographed), then on
  // "Identify your instances and get key details." -- which turns out to live
  // only in `apps/admin/hooks/use-sidebar-menu/core.ts`, i.e. in the sidebar,
  // which renders before the page has fetched anything. It passed on timing.
  //
  // `consolePage()` waits for content inside `<main>` and then asserts the
  // skeleton is gone, so neither the shell nor the error screen can satisfy it.
  const heading = page.getByRole("main").getByText("Name of instance");
  await consolePage(page, "/god-mode/general", heading);
  await expect(page.getByText(/Unable to fetch/i)).toHaveCount(0);

  // Full-viewport on purpose, and the only console story that is: this is where
  // the sidebar and the shell get their single baseline, so the other nineteen
  // can be scoped to `<main>` and stay readable.
  await capture(page, "god-mode-general", { ready: heading });
});
