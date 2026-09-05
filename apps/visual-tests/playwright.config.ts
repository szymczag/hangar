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
  // The whole-test ceiling, which must sit above the per-assertion one below or
  // it silently wins: an assertion allowed 60s inside a test allowed 30s gets
  // 30s, and the failure is reported against the assertion, which is where this
  // was mistakenly tuned twice.
  timeout: 90_000,
  fullyParallel: true,
  // Playwright defaults to half the machine's cores, which on a sixteen-core box
  // is eight browsers each booting a large React application against a single
  // API. That contention does not produce wrong screenshots -- it produces
  // hydration that does not finish inside the timeout, which reads as flakiness
  // and is really just too much at once.
  //
  // Two rather than the default, because determinism is what this suite sells
  // and the whole run is under ten seconds either way. Two against three was not
  // measurably different on the machine this was developed on, which was busy
  // with unrelated work throughout; the number to revisit if a dedicated runner
  // says otherwise is this one.
  workers: 2,
  forbidOnly: Boolean(process.env.CI),
  // Retries exist for getting the application *rendered*, not for getting a
  // screenshot to match. The flake they absorb is five Chromium instances
  // hydrating a large React app at once, one of them starved long enough to sit
  // in React Router's HydrateFallback past the timeout.
  //
  // This is not the pixel-tolerance lever wearing a different hat. A regression
  // in committed code renders the same way every attempt and fails all three.
  // What a retry *can* absorb is a screenshot taken of a half-rendered page --
  // but that is a readiness gap in the spec, and Playwright reports the test as
  // "flaky" rather than passing it silently, which is the signal to go and fix
  // the wait. Treat a flaky result as a defect with a deadline, not as a pass.
  retries: 2,
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
    // does not reach. It lives under contextOptions rather than beside the
    // other use options, which the types enforce.
    contextOptions: { reducedMotion: "reduce" },
    trace: "retain-on-failure",
  },

  expect: {
    // One timeout for every assertion in the suite. Playwright's default is 5s,
    // which is shorter than a cold boot of this application -- and because
    // helpers like settled() inherit the default while capture() passed its own,
    // the suite waited 5s in some places and 30s in others. The short waits
    // failed in bursts whenever the machine was busy, which reads as flakiness
    // rather than as the two numbers disagreeing.
    //
    // Sixty rather than thirty because a healthy assertion here resolves in
    // milliseconds -- a clean run of the whole suite is about four seconds -- so
    // the ceiling only ever applies to a boot competing for the CPU with the
    // other browsers. It is deliberately not higher: this is also how long a
    // genuinely wrong locator takes to tell you it is wrong.
    timeout: 60_000,

    toHaveScreenshot: {
      // Zero on purpose, and not to be raised. A tolerance is the mechanism by
      // which a visual suite becomes noise: it gets bumped once during a flake
      // and never comes back down. One pinned container means any difference is
      // real, so anything non-zero would only ever hide a regression.
      maxDiffPixels: 0,
      threshold: 0,
      animations: "disabled",
      // Applied to every screenshot; see the file for why the route progress
      // indicator has to be hidden rather than waited out.
      stylePath: "./screenshot.css",
      caret: "hide",
      scale: "css",
    },
  },

  projects: [
    {
      name: "chromium-1440",
      // The device descriptor carries its own 1280x720 viewport, and a project's
      // `use` overrides the top-level one -- so spreading it last silently
      // captured everything at 1280 in a project named for 1440. Re-assert the
      // viewport after the spread; the order matters.
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
  globalSetup: "./src/guards.ts",
});
