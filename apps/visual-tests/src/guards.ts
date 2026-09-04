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
export default async function globalSetup(): Promise<void> {
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

  await assertServedBundleIsSameOrigin();
}

/**
 * Refuse to run against an application that will talk to the wrong host.
 *
 * `scripts/vr.mjs` checks the built bundles before it starts the stack, which
 * is not enough on its own: the suite declares `web` and `admin` as workspace
 * dependencies (so `turbo --affected` marks it dirty when they change), and
 * `check:types` therefore pulls `web#build` and `admin#build` into its graph.
 * Running any turbo check between bringing the stack up and running the specs
 * rebuilds both SPAs with whatever environment happens to be ambient, quietly
 * replacing the bundles the edge is serving from disk.
 *
 * The symptom is every story failing on its readiness locator while the stack
 * looks perfectly healthy, because the application renders "Hangar didn't start
 * correctly" -- and if a story's locator were ever loose enough, that page is a
 * stable thing to photograph. So this asks the edge what it is actually serving
 * rather than trusting what was on disk when the stack started.
 */
async function assertServedBundleIsSameOrigin(): Promise<void> {
  const base = process.env.VR_BASE_URL;
  if (!base) return;

  const html = await (await fetch(`${base}/`)).text();
  const assets = [...html.matchAll(/["'](\/assets\/[^"']+\.js)["']/g)].map((m) => m[1]);

  const sources = await Promise.all(
    [...new Set(assets)]
      .slice(0, 12)
      .map(async (asset) => [asset, await (await fetch(`${base}${asset}`)).text()] as const)
  );

  for (const [asset, source] of sources) {
    const offender = /https?:\/\/localhost:(?:8000|3000|3001|3002|3100)/.exec(source);
    if (offender) {
      throw new Error(
        [
          `The application being served has ${offender[0]} compiled into it (${asset}),`,
          "so it is talking to a host that does not exist inside this network and is",
          "rendering its failure page. Any baseline taken now would be a photograph of",
          "that page.",
          "",
          "This usually means a turbo command rebuilt the SPAs after the stack came up:",
          "`check:types` on this package depends on `web#build` and `admin#build`.",
          "",
          "  pnpm vr:stack     rebuild and bring the stack back up correctly",
        ].join("\n")
      );
    }
  }
}
