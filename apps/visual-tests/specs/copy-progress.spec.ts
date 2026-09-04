/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * A copy in flight, on the project being copied into.
 *
 * The strip re-polls every three seconds while a copy is running, which is why
 * this stack has a broker but no celery worker: nothing advances the job, so
 * every poll returns byte-identical JSON and the DOM is stable even though the
 * network is not.
 *
 * That only holds if the seed really did leave a job mid-flight, so the counts
 * are asserted before the shot. A finished or missing job renders nothing at
 * all, and "nothing" is a stable screenshot too.
 */
test("the copy progress strip while a copy is running", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();

  await page.goto(`/${seed.workspace.slug}/projects/${seed.copyTarget.id}/issues`);

  const strip = page.getByRole("status").filter({ hasText: /cop/i });
  await expect(strip).toBeVisible();
  // The seeded job is 12 of 40. If those move, the seed changed and the
  // baseline should be reviewed rather than quietly rewritten.
  await expect(strip).toContainText("12");
  await expect(strip).toContainText("40");

  await capture(page, "copy-progress", { ready: strip, target: strip });
});
