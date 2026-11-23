/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The workspace settings and the account settings under `/settings/profile`.
 *
 * These moved to Propel in phase 3b (FORK.md ledger). Each page the move
 * restyles gets a baseline, plus the three dialogs that guard something: the
 * invitation dialog (invite policy, role cap), the workspace delete dialog (the
 * workspace's name and "delete my workspace") and the API token dialog (the
 * workspace a token acts in).
 *
 * Every story is read-only. Dialogs are opened and photographed, never
 * submitted, and nothing is typed into them, so the write guard stays quiet.
 */

/** One workspace settings page, as the workspace admin, waited on until `ready` shows. */
async function workspaceSettings(page: Page, name: string, path: string, ready: string): Promise<void> {
  const seed = fixtures();
  const main = page.getByRole("main").last();
  await page.goto(`/${seed.workspace.slug}/settings${path}`);
  const marker = main.getByText(ready, { exact: true }).first();
  await capture(page, name, { ready: marker, target: main });
}

/** One account settings tab, as the admin, waited on until `ready` shows. */
async function accountSettings(page: Page, tab: string, ready: string): Promise<void> {
  const main = page.getByRole("main").last();
  await page.goto(`/settings/profile/${tab}`);
  const marker = main.getByText(ready, { exact: true }).first();
  await capture(page, `account-settings-${tab}`, { ready: marker, target: main });
}

/** The dialog whose text includes `title`; the 1.4 and Propel dialogs name it differently. */
function dialogTitled(page: Page, title: string) {
  return page.getByRole("dialog").filter({ hasText: title });
}

test("workspace settings: general", async ({ asUser }) => {
  const page = await asUser("admin");
  await workspaceSettings(
    page,
    "workspace-settings-general",
    "",
    "When deleting a workspace, all of the data and resources within that workspace will be permanently removed and cannot be recovered."
  );
});

test("workspace settings: exports", async ({ asUser }) => {
  const page = await asUser("admin");
  await workspaceSettings(
    page,
    "workspace-settings-exports",
    "/exports",
    "Export your project data in various formats and access your export history with download links."
  );
});

test("workspace settings: webhooks", async ({ asUser }) => {
  const page = await asUser("admin");
  await workspaceSettings(page, "workspace-settings-webhooks", "/webhooks", "No Webhook added yet");
});

test("workspace settings: the invitation dialog", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/members`);
  await expect(main.getByText(seed.invitations[0])).toBeVisible();
  await main.getByRole("button", { name: "Add member", exact: true }).click();

  const dialog = dialogTitled(page, "Invite people to collaborate");
  await settled(dialog);
  await capture(page, "workspace-invite-modal", {
    ready: dialog.getByText("Invite people to collaborate", { exact: true }),
    target: dialog,
  });
});

test("workspace settings: the delete dialog", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings`);
  await expect(main.getByText("Delete this workspace", { exact: true })).toBeVisible();
  await main.getByRole("button", { name: "Delete", exact: true }).click();

  // A confirmation, so the blocks dialog is an `alertdialog`, named by its title.
  const title = "Are you sure you want to delete this workspace?";
  const dialog = page.getByRole("alertdialog", { name: title });
  await settled(dialog);
  await capture(page, "workspace-delete-modal", { ready: dialog.getByText(title, { exact: true }), target: dialog });
});

test("account settings: general", async ({ asUser }) => {
  const page = await asUser("admin");
  await accountSettings(
    page,
    "general",
    "When deactivating an account, all of the data and resources within that account will be permanently removed and cannot be recovered."
  );
});

test("account settings: preferences", async ({ asUser }) => {
  const page = await asUser("admin");
  await accountSettings(page, "preferences", "Language & Time");
});

test("account settings: notifications", async ({ asUser }) => {
  const page = await asUser("admin");
  await accountSettings(
    page,
    "notifications",
    "Stay in the loop on Work items you are subscribed to. Enable this to get notified."
  );
});

test("account settings: security", async ({ asUser }) => {
  const page = await asUser("admin");
  await accountSettings(page, "security", "New password");
});

test("account settings: API tokens", async ({ asUser }) => {
  const page = await asUser("admin");
  await accountSettings(page, "api-tokens", "No Personal token yet");
});

test("account settings: the API token dialog", async ({ asUser }) => {
  const page = await asUser("admin");
  const main = page.getByRole("main").last();

  await page.goto("/settings/profile/api-tokens");
  await expect(main.getByText("No Personal token yet", { exact: true })).toBeVisible();
  await main.getByRole("button", { name: "Add access token", exact: true }).first().click();

  const dialog = dialogTitled(page, "Create token");
  await settled(dialog);
  await capture(page, "api-token-create-modal", {
    ready: dialog.getByText("Create token", { exact: true }),
    target: dialog,
  });
});
