/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Page } from "@playwright/test";
import { capture } from "../src/capture.js";
import { test } from "../src/fixtures.js";

/**
 * The sign-in steps after the first, the password screens and onboarding.
 *
 * None of these is reachable from the seed without a write: the password and
 * code steps follow an e-mail check, and onboarding is for someone who has not
 * finished it, which every seeded persona has. So the stories answer the reads
 * that decide which screen renders, and nothing else:
 *
 *   - the e-mail check (`/auth/email-check/`) says whether the address exists
 *     and which method it signs in with. It changes nothing on the server, but
 *     it is rate limited, and an answer from the stub keeps the story from
 *     depending on the instance's sign-in settings;
 *   - for onboarding and set-password, the signed-in user, their profile and
 *     their workspace list are read from the real API and edited on the way
 *     back. Every write is still refused by the suite's guard, which is the
 *     point: onboarding finishes itself, with a PATCH, for someone who already
 *     belongs to a workspace, and a story that let that through would be
 *     photographing a different screen from the one it names.
 */

const EMAIL = "vr-reader@hangar.test";

type EmailCheck = { existing: boolean; status: "CREDENTIAL" | "MAGIC_CODE" };

async function answerEmailCheck(page: Page, answer: EmailCheck): Promise<void> {
  await page.route(
    (url) => url.pathname.endsWith("/auth/email-check/"),
    (route) => route.fulfill({ json: answer })
  );
}

async function submitEmail(page: Page): Promise<void> {
  await page.getByRole("textbox", { name: /email/i }).fill(EMAIL);
  await page.getByRole("button", { name: /continue/i }).click();
}

/** Edit a JSON response from the real API before the application reads it. */
async function rewrite<T>(page: Page, pathname: string, edit: (body: T) => T): Promise<void> {
  await page.route(
    (url) => url.pathname === pathname,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      const response = await route.fetch();
      const body = (await response.json()) as T;
      await route.fulfill({ response, json: edit(body) });
    }
  );
}

type OnboardingSteps = {
  profile_complete: boolean;
  workspace_create: boolean;
  workspace_invite: boolean;
  workspace_join: boolean;
};

/** A signed-in person who has not finished onboarding and belongs to no workspace yet. */
async function notOnboarded(page: Page, steps: Partial<OnboardingSteps> = {}): Promise<void> {
  await rewrite<Record<string, unknown>>(page, "/api/users/me/", (user) => ({ ...user, is_password_autoset: true }));
  await rewrite<Record<string, unknown>>(page, "/api/users/me/profile/", (profile) => ({
    ...profile,
    is_onboarded: false,
    onboarding_step: {
      profile_complete: false,
      workspace_create: false,
      workspace_invite: false,
      workspace_join: false,
      ...steps,
    },
  }));
  await rewrite<unknown[]>(page, "/api/users/me/workspaces/", () => []);
  await rewrite<unknown[]>(page, "/api/users/me/workspaces/invitations/", () => []);
}

test("sign-in: the password step", async ({ page }) => {
  await answerEmailCheck(page, { existing: true, status: "CREDENTIAL" });
  await page.goto("/");
  await submitEmail(page);
  await capture(page, "sign-in-password", { ready: page.locator("#password") });
});

test("sign-in: the unique code step", async ({ page }) => {
  await answerEmailCheck(page, { existing: true, status: "MAGIC_CODE" });
  // With SMTP configured the step asks the server to e-mail a code. That stores
  // a code and sends mail, so it is answered here instead.
  await page.route(
    (url) => url.pathname.endsWith("/auth/magic-generate/"),
    (route) => route.fulfill({ json: {} })
  );
  await page.goto("/");
  await submitEmail(page);
  await capture(page, "sign-in-unique-code", { ready: page.locator("#unique-code") });
});

/**
 * The strength meter is the fork's asynchronous zxcvbn estimate, not upstream's
 * synchronous one (FORK.md S9). A sixteen-character run of one letter passes the
 * length rule and fails the estimate, so the story shows both criteria and the
 * estimator's own warning -- which only appears once the estimate has resolved,
 * and is therefore what the story waits for.
 */
test("sign-up: the password step with the strength meter", async ({ page }) => {
  await answerEmailCheck(page, { existing: false, status: "CREDENTIAL" });
  await page.goto("/sign-up");
  await submitEmail(page);
  await page.locator("#password").fill("a".repeat(16));
  await capture(page, "sign-up-password", { ready: page.getByText(/repeated characters/i) });
});

test("forgot password", async ({ page }) => {
  await page.goto(`/accounts/forgot-password?email=${encodeURIComponent(EMAIL)}`);
  await capture(page, "forgot-password", { ready: page.getByRole("button", { name: /reset link/i }) });
});

test("reset password", async ({ page }) => {
  await page.goto(`/accounts/reset-password?uidb64=MQ&token=vr-token&email=${encodeURIComponent(EMAIL)}`);
  await capture(page, "reset-password", { ready: page.locator("#password") });
});

test("set password", async ({ asUser }) => {
  const page = await asUser("light");
  await rewrite<Record<string, unknown>>(page, "/api/users/me/", (user) => ({ ...user, is_password_autoset: true }));
  await page.goto("/accounts/set-password");
  await capture(page, "set-password", { ready: page.locator("#password") });
});

test("set password: an account bound to an identity provider", async ({ asUser }) => {
  const page = await asUser("light");
  await rewrite<Record<string, unknown>>(page, "/api/users/me/", (user) => ({
    ...user,
    is_password_autoset: true,
    is_federated: true,
  }));
  await page.goto("/accounts/set-password");
  await capture(page, "set-password-federated", {
    ready: page.getByText("This account signs in through an identity provider"),
  });
});

test("onboarding: the profile step", async ({ asUser }) => {
  const page = await asUser("light");
  await notOnboarded(page);
  await page.goto("/onboarding");
  await capture(page, "onboarding-profile", { ready: page.getByText("Create your profile.") });
});

test("onboarding: the workspace step", async ({ asUser }) => {
  const page = await asUser("light");
  await notOnboarded(page, { profile_complete: true });
  await page.goto("/onboarding");
  await capture(page, "onboarding-workspace", {
    ready: page.getByText(/Create your workspace|only lets administrators create them/),
  });
});
