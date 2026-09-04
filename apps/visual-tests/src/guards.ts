/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

/**
 * Refuse to compare screenshots outside the environment they were taken in.
 *
 * Baselines are only meaningful against one browser build and one set of fonts.
 * Rather than manage that difference with a pixel tolerance -- which hides real
 * regressions and only ever gets raised -- the suite declines to run anywhere
 * else, and says so in one line instead of producing thirty mystifying diffs.
 */
export default function globalSetup(): void {
  const updating = process.argv.includes("--update-snapshots") || process.argv.includes("-u");
  const inContainer = process.env.VR_IN_CONTAINER === "1";

  if (!inContainer && !updating) {
    throw new Error(
      [
        "Visual tests compare against baselines captured in a pinned container,",
        "so running them anywhere else reports differences that are about this",
        "machine rather than about the code.",
        "",
        "  pnpm vr           runs them in that container",
        "  pnpm vr:update    the only supported way to change a baseline",
      ].join("\n")
    );
  }

  // A stale image is a single loud failure rather than a suite-wide diff.
  const expected = require("@playwright/test/package.json").version as string;
  const actual = process.env.VR_PLAYWRIGHT_VERSION;
  if (inContainer && actual && actual !== expected) {
    throw new Error(
      `The container runs Playwright ${actual} but this package expects ${expected}. ` +
        "Bump the image tag in docker-compose-visual.yml and the catalog entry together."
    );
  }
}
