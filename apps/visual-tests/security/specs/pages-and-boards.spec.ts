/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { createPage, createWorkItem, openPage, post, projectId, signIn, slug } from "../src/app";
import { attachDiagnostics, enforceContentSecurityPolicy, watch } from "../src/enforce";

// The surfaces served by something other than the single-page apps' nginx:
// published boards (space renders them on the server, with a nonce policy of
// its own), pages (edited through the live server's WebSocket) and the PDF
// export (rendered by live, downloaded by the page).

test.beforeEach(async ({ context }) => {
  await enforceContentSecurityPolicy(context);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachDiagnostics(page, testInfo);
});

test("a published board renders a work item with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const workItem = await createWorkItem(context.request, baseURL!, "Trusted Types: published");
  const board = await post(
    context.request,
    baseURL!,
    `/api/workspaces/${slug}/projects/${projectId}/project-deploy-boards/`,
    {}
  );
  // Read as the public reads it: without an account.
  await context.clearCookies();
  const reports = watch(page);

  await page.goto(`/spaces/issues/${board.anchor}/?peekId=${workItem.id}`);
  const description = page.locator(".ProseMirror", { hasText: "legacy cell" });
  await expect(description.locator('td[data-background-color="purple"]')).toBeVisible();
  await expect(description.locator('p[data-text-align="center"]')).toHaveCSS("text-align", "center");

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("a page edits through the live server with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const created = await createPage(context.request, baseURL!, "Trusted Types: page");
  const reports = watch(page);

  const editor = await openPage(page, created.id);
  await editor.getByText("last paragraph").click();
  await page.keyboard.press("End");
  await page.keyboard.type(" typed through live");
  await expect(editor.getByText("last paragraph typed through live")).toBeVisible();

  // Stored by live, not by the browser: the text reaches the API only if the
  // collaboration connection works under the policy.
  await expect
    .poll(async () => {
      const response = await context.request.get(`/api/workspaces/${slug}/projects/${projectId}/pages/${created.id}/`);
      return (await response.json()).description_html as string;
    })
    .toContain("typed through live");

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("a page exports to PDF with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const name = "Trusted Types: export";
  const created = await createPage(context.request, baseURL!, name);
  const reports = watch(page);

  await openPage(page, created.id);
  // The page's own menu: the one in the header row that carries its name, not
  // the sidebar's or the editor's drag handles.
  const menu = page.locator("button:has(svg.lucide-ellipsis)");
  await page.locator("div").filter({ hasText: name }).filter({ has: menu }).last().locator(menu).click();
  await page.getByRole("menuitem", { name: "Export" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "PDF" })).toBeVisible();
  const download = page.waitForEvent("download");
  await dialog.getByRole("button", { name: "Export" }).click();
  const file = await (await download).path();
  expect(readFileSync(file).subarray(0, 5).toString("latin1")).toBe("%PDF-");

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});
