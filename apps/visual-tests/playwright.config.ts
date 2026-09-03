/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { defineConfig, devices } from "@playwright/test";

/**
 * Visual regression against the real application.
 *
 * Everything here exists to make one screenshot comparable to another taken on
 * a different machine on a different day. The suite only ever runs inside a
 * pinned container (see src/guards.ts), which is what turns font rendering from
 * something to manage into something that cannot vary.
 */
export default defineConfig({
  testDir: "./specs",
  // Baselines live beside the suite, not beside each spec, and carry no
  // platform segment: exactly one environment is supported, and the path makes
  // that structurally obvious rather than a convention someone has to know.
  snapshotPathTemplate: "{testDir}/../baselines/{testFileName}/{arg}{ext}",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [["html", { open: "never" }], ["list"]] : [["list"]],

  use: {
    baseURL: process.env.VR_BASE_URL ?? "http://vr-edge",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    timezoneId: "UTC",
    locale: "en-US",
    // Only reaches the logged-out surfaces: a signed-in user's theme comes from
    // their stored profile, which the seed sets per user.
    colorScheme: "light",
    // framer-motion animates in JavaScript, which `animations: "disabled"`
    // does not reach.
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },

  expect: {
    toHaveScreenshot: {
      // Zero on purpose, and not to be raised. A tolerance is the mechanism by
      // which a visual suite becomes noise: it gets bumped once during a flake
      // and never comes back down. One pinned container means any difference is
      // real, so anything non-zero would only ever hide a regression.
      maxDiffPixels: 0,
      threshold: 0,
      animations: "disabled",
      caret: "hide",
      scale: "css",
    },
  },

  projects: [{ name: "chromium-1440", use: { ...devices["Desktop Chrome"] } }],
  globalSetup: "./src/guards.ts",
});
