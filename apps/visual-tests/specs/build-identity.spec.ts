/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The dialog behind the edition badge, at two widths.
 *
 * This is the renders-but-wrong story, and it is here because it is the one
 * surface with a track record. It always rendered, always passed whatever tests
 * existed, and was still wrong twice: once because it looked wrong, which is
 * what prompted this suite, and once because it silently showed no release notes
 * at all -- the bundled version and the version the API reports were compared
 * with `===`, and one of them carried a leading `v`.
 *
 * So the story asserts the notes are actually there before it captures. An empty
 * notes section is a perfectly stable screenshot of the bug.
 *
 * It also exercises the 300ms modal transition, which `toBeVisible()` is
 * satisfied by at the very start of.
 */
for (const [name, width] of [
  ["wide", 1440],
  ["narrow", 768],
] as const) {
  test(`the build identity dialog (${name})`, async ({ asUser }) => {
    const page = await asUser("light");
    await page.setViewportSize({ width, height: 900 });
    const seed = fixtures();

    await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/issues`);

    // The backdrop behind this dialog is only 30% opaque
    // (`oklch(0.1482 0.0034 196.79 / 0.3)`), so the corners outside the panel's
    // border radius are seven parts the page underneath to three parts backdrop.
    // That makes the work-item list part of this photograph whether the story
    // means it or not, and nothing here used to wait for it: the badge below
    // lives in the sidebar footer and is visible long before the list arrives.
    // A run that opened the dialog first captured a blank content pane through
    // the backdrop and failed all three attempts on ~750 pixels.
    await expect(page.getByText(seed.workItems[0], { exact: false }).first()).toBeVisible();

    // The badge lives in the sidebar footer and doubles as the trigger.
    const badge = page.getByRole("button", { name: /Hangar by @szymczag/i }).first();
    await expect(badge).toBeVisible();
    await badge.click();

    // The element carrying role="dialog" is Headless UI's outermost wrapper --
    // `relative z-30` with no size of its own, so it is never "visible" and is
    // the wrong thing to photograph. The panel is the dialog as anyone looking
    // at the screen means it, and it is also the element that transitions.
    await expect(page.getByRole("dialog")).toHaveCount(1);
    const dialog = page.locator('[id^="headlessui-dialog-panel"]');
    await settled(dialog);

    // The notes are the point. Without this the story happily records the
    // "release notes unavailable" state, which is exactly the shipped defect.
    const notes = dialog.getByRole("listitem");
    await expect(notes.first()).toBeVisible();
    expect(await notes.count()).toBeGreaterThan(0);

    await capture(page, `build-identity-${name}`, { ready: notes.first(), target: dialog });
  });
}
