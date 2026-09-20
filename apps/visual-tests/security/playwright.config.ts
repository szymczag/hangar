/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { defineConfig } from "@playwright/test";
import visual from "../playwright.config";

/**
 * The security suite: the real application with its Content-Security-Policy
 * and Trusted Types enforced (docs/trusted-types-plan.md, phases 3 and 4).
 *
 * It shares the visual suite's stack, browser and timeouts, and runs after it:
 * unlike the visual suite it writes (work items, comments, stickies, pages, a
 * published board), so it must never run beside it. One worker, in file order.
 */
export default defineConfig({
  ...visual,
  testDir: "./specs",
  // Relative paths resolve against this file, not the visual config's. The
  // visual suite's guards run first; see the file for what else it waits for.
  globalSetup: "./src/setup.ts",
  expect: {
    ...visual.expect,
    toHaveScreenshot: { ...visual.expect?.toHaveScreenshot, stylePath: "../screenshot.css" },
  },
  fullyParallel: false,
  workers: 1,
  // Each test runs twice: with the default policy observing (the default,
  // HANGAR_CSP_TRUSTED_TYPES=report) and sanitizing (=enforce). The browser
  // enforces Trusted Types in both; what differs is what the policy returns.
  projects: [
    { ...visual.projects![0], name: "trusted-types-report", metadata: { trustedTypes: "report" } },
    { ...visual.projects![0], name: "trusted-types-enforce", metadata: { trustedTypes: "enforce" } },
  ],
  use: {
    ...visual.use,
    launchOptions: {
      ...visual.use?.launchOptions,
      args: [
        ...(visual.use?.launchOptions?.args ?? []),
        // Documents are fulfilled by the suite (to add the policy headers), which
        // Chromium places in the public address space; the assets they load from
        // vr-edge would then count as more private and be blocked.
        "--disable-features=BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights,PrivateNetworkAccessRespectPreflightResults,LocalNetworkAccessChecks",
      ],
    },
  },
});
