/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test, type Page } from "@playwright/test";
import { createWorkItem, expectOnlyHostileObservations, post, projectId, seed, signIn, slug } from "../src/app";
import { attachDiagnostics, enforceContentSecurityPolicy, watch } from "../src/enforce";

// The application under its own Content-Security-Policy with Trusted Types
// enforced (docs/trusted-types-plan.md, phases 3 and 4). Every string that
// reaches a guarded DOM sink must come through a policy, or the page throws.
// What the default policy reports is checked too: ordinary content must pass
// DOMPurify unchanged, and only hostile content may produce a report -- in the
// report project as an observation, in the enforce project as a removal.

/** A paste event carrying the given clipboard flavours, dispatched on the editor. */
async function paste(page: Page, flavours: Record<string, string>) {
  await page.evaluate((data) => {
    const transfer = new DataTransfer();
    for (const [type, value] of Object.entries(data)) transfer.setData(type, value);
    document
      .querySelector(".ProseMirror")!
      .dispatchEvent(new ClipboardEvent("paste", { clipboardData: transfer, bubbles: true, cancelable: true }));
  }, flavours);
}

test.beforeEach(async ({ context }) => {
  await enforceContentSecurityPolicy(context);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachDiagnostics(page, testInfo);
});

test("the rich-text editor renders, edits and pastes with Trusted Types enforced", async ({
  page,
  context,
  baseURL,
}) => {
  await signIn(context, baseURL!);
  const workItem = await createWorkItem(context.request, baseURL!, "Trusted Types: editor");
  const reports = watch(page);

  await page.goto(`/${slug}/browse/${seed.project.identifier}-${workItem.sequence_id}/`);
  const editor = page.locator(".ProseMirror").first();
  await expect(editor.getByText("legacy cell")).toBeVisible();
  await expect(editor.locator('td[data-background-color="purple"]')).toBeVisible();
  await expect(editor.locator('p[data-text-align="center"]')).toHaveCSS("text-align", "center");

  // Typing and a formatting shortcut.
  await editor.getByText("last paragraph").click();
  await page.keyboard.press("End");
  await page.keyboard.type(" typed in the browser");
  await page.keyboard.press("ControlOrMeta+Shift+E");
  await expect(editor.locator('p[data-text-align="center"]', { hasText: "typed in the browser" })).toBeVisible();

  // Markdown pasted from an application that also writes plain HTML.
  await paste(page, {
    "text/plain": "## Pasted heading\n\n- first\n- second",
    "text/html": "<meta charset='utf-8'><div>## Pasted heading</div><div>- first</div><div>- second</div>",
  });
  await expect(editor.getByRole("heading", { name: "Pasted heading" })).toBeVisible();

  // Hostile pastes: the editor's own clipboard flavour, and plain HTML that
  // goes through ProseMirror's clipboard parser. Neither may run anything.
  await page.evaluate(() => {
    (window as unknown as { __pwned: number }).__pwned = 0;
  });
  await paste(page, {
    "text/plain": "one",
    "text/plane-editor-html": '<p>one</p><img src="x" onerror="window.__pwned=1">',
  });
  await paste(page, {
    "text/plain": "two",
    "text/html": '<p>two</p><img src="y" onerror="window.__pwned=2"><svg onload="window.__pwned=3"></svg>',
  });
  await expect.poll(() => page.evaluate(() => (window as unknown as { __pwned: number }).__pwned)).toBe(0);

  // The description saves through the API as usual.
  await expect
    .poll(async () => {
      const response = await context.request.get(
        `/api/workspaces/${slug}/projects/${projectId}/issues/${workItem.id}/`
      );
      return (await response.json()).description_html as string;
    })
    .toContain("typed in the browser");

  await reports.expectClean();
  // Ordinary content passed DOMPurify unchanged; the hostile pastes are what
  // the default policy reported, and nothing else.
  expect(reports.observations.length).toBeGreaterThan(0);
  expectOnlyHostileObservations(reports.observations);
});

test("a comment renders with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const workItem = await createWorkItem(context.request, baseURL!, "Trusted Types: comment");
  await post(
    context.request,
    baseURL!,
    `/api/workspaces/${slug}/projects/${projectId}/issues/${workItem.id}/comments/`,
    {
      comment_html: '<p>a <strong>rich</strong> comment with <a href="https://example.com">a link</a></p>',
    }
  );
  const reports = watch(page);

  await page.goto(`/${slug}/browse/${seed.project.identifier}-${workItem.sequence_id}/`);
  await expect(page.getByText("comment with").first()).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("a sticky renders and edits with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  await post(context.request, baseURL!, `/api/workspaces/${slug}/stickies/`, {
    name: "Trusted Types: sticky",
    description_html:
      '<p>sticky <strong>note</strong> <span data-text-color="gray">gray</span></p><ul><li><p>item</p></li></ul>',
  });
  const reports = watch(page);

  await page.goto(`/${slug}/stickies/`);
  const editor = page.locator(".ProseMirror", { hasText: "sticky note" }).first();
  await expect(editor.locator('span[data-text-color="gray"]')).toBeVisible();
  await editor.getByText("item").click();
  await page.keyboard.press("End");
  await page.keyboard.type(" typed");
  await expect(editor.getByText("item typed")).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("the workspace home renders with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const reports = watch(page);

  await page.goto(`/${slug}/`);
  await expect(page.getByRole("main").last().getByText(seed.sharedLinks.visible[0]).first()).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("the instance console renders with Trusted Types enforced", async ({ page, baseURL }) => {
  await page.context().addCookies([
    {
      name: "admin-session-id",
      value: seed.users.admin.adminSessionCookie!,
      url: baseURL!,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  const reports = watch(page);

  await page.goto("/god-mode/general/");
  await expect(page.getByRole("main").getByText("Name of instance")).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});
