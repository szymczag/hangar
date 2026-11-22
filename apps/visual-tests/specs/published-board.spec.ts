/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Page } from "@playwright/test";
import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The published board (apps/space), as the public reads it: no session.
 *
 * Space is the one frontend rendered on the server, with a per-request nonce
 * in its policy, and since the move to Propel it is built from the same
 * components as God Mode. The policy guard holds every story here to zero
 * violations; the stories below hold the layout.
 *
 * The seeded board has no assignees on purpose: which properties a public card
 * shows is decided in apps/space/helpers/display-properties.helper.ts, and the
 * due-date colours depend on the clock, which is why it is fixed here as in
 * the signed-in stories.
 */
async function openBoard(page: Page, query = "") {
  const seed = fixtures();
  await page.clock.setFixedTime(new Date(seed.clock));
  await page.goto(`/spaces/issues/${seed.publishedBoard.anchor}/${query}`);
  return seed.publishedBoard;
}

test("the published board as a list", async ({ page }) => {
  const board = await openBoard(page);

  const last = page.getByText(board.workItems.at(-1)!, { exact: true });
  await expect(page.getByText(board.workItems[0], { exact: true })).toBeVisible();
  await capture(page, "published-board-list", { ready: last });
});

test("the published board as a board", async ({ page }) => {
  const board = await openBoard(page);

  await page.getByRole("button", { name: "Board", exact: true }).click();
  const last = page.getByText(board.workItems.at(-1)!, { exact: true });
  await expect(page.getByRole("button", { name: "Board", exact: true })).toHaveAttribute("aria-pressed", "true");
  await capture(page, "published-board-kanban", { ready: last });
});

test("a work item opened from the published board", async ({ page }) => {
  const board = await openBoard(page, `?peekId=${fixtures().publishedBoard.peekId}`);

  // The list behind the panel loads on its own; until it has, the left half is
  // the board's loader, which is a different picture of the same story.
  await expect(page.getByText(board.workItems[1], { exact: true })).toBeVisible();
  const title = page.getByRole("heading", { name: board.workItems[0] });
  await capture(page, "published-board-peek", { ready: title });
});

/**
 * Space renders on the server and React hydrates that HTML; a first client
 * render that differs (React #418, #423, #425) is a page error in production.
 * Two loads, so the second runs with every chunk already fetched, which is the
 * timing that exposed the God Mode error. No screenshot.
 */
test("the published board hydrates cleanly", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error" && /hydrat|#41[89]|#42[35]/i.test(message.text())) errors.push(message.text());
  });

  for (const _ of [1, 2]) {
    // oxlint-disable-next-line eslint/no-await-in-loop -- the second load must follow the first
    const board = await openBoard(page);
    // oxlint-disable-next-line eslint/no-await-in-loop -- see above
    await expect(page.getByText(board.workItems[0], { exact: true })).toBeVisible();
  }

  expect(errors).toEqual([]);
});
