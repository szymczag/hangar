/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { defineConfig } from "@playwright/test";
import visual from "../playwright.config";

/**
 * The security suite: the real application with its Content-Security-Policy
 * and Trusted Types enforced (docs/trusted-types-plan.md, phase 3).
 *
 * It shares the visual suite's stack, browser and timeouts, and runs after it:
 * unlike the visual suite it writes (work items, comments), so it must never
 * run beside it. One worker, in file order.
 */
export default defineConfig({
  ...visual,
  testDir: "./specs",
  // Relative paths resolve against this file, not the visual config's; the
  // container guard still runs first.
  globalSetup: "../src/guards.ts",
  expect: {
    ...visual.expect,
    toHaveScreenshot: { ...visual.expect?.toHaveScreenshot, stylePath: "../screenshot.css" },
  },
  fullyParallel: false,
  workers: 1,
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
