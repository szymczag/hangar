/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test } from "@playwright/test";
import { createPage, openPage, signIn } from "../src/app";
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
