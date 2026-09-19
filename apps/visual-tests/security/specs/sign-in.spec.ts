/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test } from "@playwright/test";
import { seed, slug } from "../src/app";
import { attachDiagnostics, enforceContentSecurityPolicy, watch } from "../src/enforce";

// Signing in through the real forms. They are HTML form posts to the API,
// which answers with a redirect; form-action applies to the post and, in
// Chrome, to where the redirect leads. A redirect off the page's origin is
// refused, and the sign-in silently does nothing.
//
// The browser follows those redirects itself, and Playwright does not route a
// redirected request again, so the page signed in to arrives straight from the
// edge (which enforces the same policy, but without the suite's Trusted Types
// mode). Each test checks that page, then reloads it through the suite.

const PASSWORD = "visual-regression";

test.beforeEach(async ({ context }) => {
  await enforceContentSecurityPolicy(context);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachDiagnostics(page, testInfo);
});

test("signing in to the web app with a password", async ({ page }) => {
  const reports = watch(page);
  await page.goto("/");
  await page.getByRole("textbox", { name: "Email" }).fill(seed.users.light.email);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("textbox", { name: "Password" }).fill(PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page).toHaveURL(new RegExp(`/${slug}/`));
  await reports.expectNoViolations();
  await page.reload();
  await expect(page.getByRole("main").last()).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("signing in to the instance console with a password", async ({ page }) => {
  const reports = watch(page);
  await page.goto("/god-mode/");
  await page.getByRole("textbox", { name: "Email" }).fill(seed.users.admin.email);
  await page.getByRole("textbox", { name: "Password" }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  // The console asks for a security key next (the seeded admin has none);
  // reaching that screen means the post and its redirect were allowed.
  await expect(page).not.toHaveURL(/\/god-mode\/?$/);
  await expect(page).toHaveURL(/\/god-mode\//);
  await expect(page.getByRole("heading", { name: "Register a security key" })).toBeVisible();
  await reports.expectNoViolations();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Register a security key" })).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("signing in to a published board with a password", async ({ page }) => {
  const reports = watch(page);
  await page.goto("/spaces/");
  await page.getByRole("textbox", { name: "Email" }).fill(seed.users.light.email);
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("textbox", { name: "Password" }).fill(PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("button", { name: "VR Light" })).toBeVisible();
  await reports.expectNoViolations();
  await page.reload();
  await expect(page.getByRole("button", { name: "VR Light" })).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});
