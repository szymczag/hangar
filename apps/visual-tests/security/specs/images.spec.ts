/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test } from "@playwright/test";
import { post, projectId, seed, signIn, slug } from "../src/app";
import { attachDiagnostics, enforceContentSecurityPolicy, readViolations, watch } from "../src/enforce";

// Images are only this instance's own (docs/content-security-policy.md): an
// image a description points at on another host is refused by img-src, and
// that is the only thing on the page that is.

test.beforeEach(async ({ context }) => {
  await enforceContentSecurityPolicy(context);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachDiagnostics(page, testInfo);
});

test("an image from another host is not loaded", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const workItem = await post(context.request, baseURL!, `/api/workspaces/${slug}/projects/${projectId}/issues/`, {
    name: "Images: another host",
    description_html: '<p>before the image</p><img src="https://images.example/picture.png"><p>after the image</p>',
  });
  const reports = watch(page);

  await page.goto(`/${slug}/browse/${seed.project.identifier}-${workItem.sequence_id}/`);
  await expect(page.locator(".ProseMirror").first().getByText("after the image")).toBeVisible();
  // The editor renders the image more than once; each attempt is refused.
  await expect
    .poll(async () => [
      ...new Set((await readViolations(page)).map((violation) => `${violation.directive} ${violation.blocked}`)),
    ])
    .toEqual(["img-src https://images.example/picture.png"]);
  expect(reports.observations).toEqual([]);
});
