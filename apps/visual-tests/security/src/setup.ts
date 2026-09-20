/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import guards from "../../src/guards";

// IFA_F_TENTATIVE: an IPv6 address still in duplicate address detection.
const TENTATIVE = 0x40;

const tentativeAddresses = () => {
  try {
    return readFileSync("/proc/net/if_inet6", "utf8")
      .split("\n")
      .filter((line) => line.trim() && Number.parseInt(line.trim().split(/\s+/)[4], 16) & TENTATIVE);
  } catch {
    return [];
  }
};

/**
 * The visual suite's guards, then a network that has stopped changing.
 *
 * A fresh container's link-local IPv6 address is tentative for about two
 * seconds. When it settles, Chromium sees a network change and fails every
 * request in flight with ERR_NETWORK_CHANGED -- which, in the first test to
 * run, left the application on its splash screen until the timeout. This suite
 * has no retries to spare for that, so it waits for the address instead.
 */
export default async function globalSetup(): Promise<void> {
  await guards();
  for (let waited = 0; tentativeAddresses().length > 0 && waited < 15_000; waited += 250) {
    // oxlint-disable-next-line eslint/no-await-in-loop -- polling, one at a time by definition
    await sleep(250);
  }
}
