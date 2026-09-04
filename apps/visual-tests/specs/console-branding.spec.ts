/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture, consolePage } from "../src/capture.js";
import { test } from "../src/fixtures.js";

/**
 * The two console pages that decide what everyone else sees.
 *
 * Branding writes the sign-in screen and the failure pages; the maintenance
 * form writes the strip that sits above the entire application. Both are
 * wholly fork-owned (FORK.md rows 41, 42, 61, 63, 71, 74), and both are long
 * forms of switches whose copy carries real consequences -- the licence-notice
 * switch explains where the AGPL source offer moves to when it is turned off.
 * Wording that long is worth photographing: it is the kind of thing that gets
 * reflowed by accident.
 */
const PAGES = [
  ["branding", "branding", "Organisation name"],
  ["maintenance", "maintenance", "Starts (optional)"],
] as const;

for (const [name, path, readyText] of PAGES) {
  test(`the console page: ${name}`, async ({ asAdmin }) => {
    const page = await asAdmin();
    const main = page.getByRole("main");

    await consolePage(page, `/god-mode/${path}`, main.getByText(readyText).first());

    await capture(page, `console-${name}`, {
      ready: main.getByText(readyText).first(),
      target: main,
    });
  });
}
