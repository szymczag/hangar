/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * Workspace members, with invitations outstanding.
 *
 * The pending block renders only for an admin and only when at least one invite
 * is outstanding, so an unseeded instance photographs a members table and
 * nothing else -- which is the state this surface was in when its collapsible
 * was reported stuck open and empty (FORK.md row 58).
 *
 * "Pending" is not a stored state. The endpoint returns every invitation that
 * has not been revoked and the row is labelled unconditionally, so the seed
 * only has to leave them unanswered.
 */
test("pending invitations in workspace members", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/members`);

  await Promise.all(seed.invitations.map((email) => expect(main.getByText(email)).toBeVisible()));

  await capture(page, "workspace-members-invitations", {
    ready: main.getByText(seed.invitations[0]),
    target: main,
  });
});
