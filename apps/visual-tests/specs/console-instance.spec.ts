/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture, consolePage } from "../src/capture.js";
import { test } from "../src/fixtures.js";

/**
 * The instance-wide console pages.
 *
 * `general` is deliberately absent: it is the one page captured full-viewport,
 * by `god-mode.spec.ts`, so that the console shell and sidebar have exactly one
 * baseline between them rather than nineteen.
 *
 * Two of these photograph seeded content rather than an empty form -- the
 * workspace list shows the seeded workspace and the user list the seeded
 * accounts -- so a seed that stopped producing them fails here instead of
 * quietly recording an empty table.
 */
const PAGES = [
  ["email", "email", "Email delivery ledger"],
  ["workspace", "workspace", "Hangar VR"],
  ["workspace-create", "workspace/create", "Name your workspace"],
  ["users", "users", "vr-admin@hangar.test"],
  ["ai", "ai", "LLM Model"],
  ["image", "image", "Access key from your Unsplash account"],
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
