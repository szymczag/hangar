/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test } from "@playwright/test";
import { createPage, openPage, seed, signIn } from "../src/app";
import { attachDiagnostics, enforceContentSecurityPolicy, watch } from "../src/enforce";

// Nothing the application needs comes from another host. The emoji picker is
// the case that used to: its data was fetched from a public CDN, which told a
// third party who was using the deployment (docs/content-security-policy.md).

test.beforeEach(async ({ context }) => {
  await enforceContentSecurityPolicy(context);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachDiagnostics(page, testInfo);
});

test("the emoji picker reads its data from this instance, and nothing leaves it", async ({
  page,
  context,
  baseURL,
}) => {
  await signIn(context, baseURL!);
  const created = await createPage(context.request, baseURL!, "Third party: emoji picker");
  const reports = watch(page);
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));

  await openPage(page, created.id);
  await page.getByRole("button", { name: "Icon" }).first().click();
  // It opens on the bundled icons; the emoji tab is the one that fetches.
  await page.getByRole("tab", { name: "Emoji" }).click();

  // The picker renders what it fetched.
  const picker = page.locator('[data-slot="emoji-picker"]');
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("button").first()).toBeVisible();
  expect(requested.filter((url) => url.endsWith("/emojibase/en/data.json"))).toHaveLength(1);

  const origin = new URL(baseURL!).origin;
  expect(requested.filter((url) => !url.startsWith(origin) && !url.startsWith("data:"))).toEqual([]);
  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

// The published boards use @plane/blocks' reaction picker, which is frimousse
// underneath too; without the data URL space sets at start-up it would fetch
// from the CDN. Opening it needs no account, so the board is read as the
// public reads it, and no reaction is chosen.
test("the reaction picker on a published board reads its data from this instance", async ({ page, baseURL }) => {
  const board = seed.publishedBoard;
  const reports = watch(page);
  const requested: string[] = [];
  page.on("request", (request) => requested.push(request.url()));

  await page.goto(`/spaces/issues/${board.anchor}/?peekId=${board.peekId}`);
  await expect(page.getByRole("heading", { name: board.workItems[0] })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Add reaction", exact: true }).click();

  const picker = page.locator('[data-slot="emoji-picker"]');
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("button").first()).toBeVisible();
  expect(requested.filter((url) => url.endsWith("/spaces/emojibase/en/data.json"))).toHaveLength(1);

  const origin = new URL(baseURL!).origin;
  expect(requested.filter((url) => !url.startsWith(origin) && !url.startsWith("data:"))).toEqual([]);
  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});
