/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { fixtures } from "../../src/manifest.js";
import { attachDiagnostics, enforceContentSecurityPolicy, watch } from "../src/enforce";

// The application under its own Content-Security-Policy with Trusted Types
// enforced (docs/trusted-types-plan.md, phase 3). Every string that reaches a
// guarded DOM sink must come through a policy, or the page throws. The
// default policy observes in this phase, so what it may report is also
// checked: ordinary content must pass DOMPurify unchanged, and only hostile
// content may produce an observation.

const seed = fixtures();
const slug = seed.workspace.slug;
const projectId = seed.project.id;

const RICH_DESCRIPTION = [
  '<h2>Heading</h2><p data-text-align="center">centred paragraph</p>',
  '<p><strong>bold</strong> <em>italic</em> <span data-text-color="gray">gray</span> ',
  '<span data-background-color="peach">peach</span> <a href="https://example.com/doc">a link</a></p>',
  "<ul><li><p>bullet</p></li></ul><ol><li><p>numbered</p></li></ol>",
  '<ul data-type="taskList"><li data-type="taskItem" data-checked="true"><label><input type="checkbox" checked><span></span></label><div><p>task</p></div></li></ul>',
  '<blockquote><p>quoted</p></blockquote><pre><code class="language-ts">const x = 1;</code></pre><hr>',
  '<table><tbody><tr><th data-background-color="green"><p>head</p></th><th><p>plain</p></th></tr>',
  '<tr><td background="var(--editor-colors-purple-background)"><p>legacy cell</p></td><td><p>cell</p></td></tr></tbody></table>',
  "<p>last paragraph</p>",
].join("");

async function signIn(page: Page, baseURL: string) {
  await page
    .context()
    .addCookies([
      { name: "session-id", value: seed.users.light.sessionCookie!, url: baseURL, httpOnly: true, sameSite: "Lax" },
    ]);
}

async function createWorkItem(request: APIRequestContext, baseURL: string, name: string) {
  const csrf = await (await request.get("/auth/get-csrf-token/")).json();
  const response = await request.post(`/api/workspaces/${slug}/projects/${projectId}/issues/`, {
    headers: { "X-CSRFToken": csrf.csrf_token, Referer: `${baseURL}/` },
    data: { name, description_html: RICH_DESCRIPTION },
  });
  expect(response.status(), await response.text()).toBe(201);
  const workItem = await response.json();
  return { workItem, csrf: csrf.csrf_token as string };
}

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
  await signIn(page, baseURL!);
  const { workItem, csrf } = await createWorkItem(context.request, baseURL!, "Trusted Types: editor");
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
        `/api/workspaces/${slug}/projects/${projectId}/issues/${workItem.id}/`,
        { headers: { "X-CSRFToken": csrf } }
      );
      return (await response.json()).description_html as string;
    })
    .toContain("typed in the browser");

  await reports.expectClean();
  // Ordinary content passed DOMPurify unchanged; the hostile pastes are what
  // the observing default policy reported, and nothing else.
  expect(reports.observations.length).toBeGreaterThan(0);
  for (const observation of reports.observations) {
    expect(observation["violated-directive"]).toBe("html-would-change");
    expect(observation["script-sample"]).toMatch(/onerror|onload/);
  }
});

test("a comment renders with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(page, baseURL!);
  const { workItem, csrf } = await createWorkItem(context.request, baseURL!, "Trusted Types: comment");
  const comment = await context.request.post(
    `/api/workspaces/${slug}/projects/${projectId}/issues/${workItem.id}/comments/`,
    {
      headers: { "X-CSRFToken": csrf, Referer: `${baseURL}/` },
      data: { comment_html: '<p>a <strong>rich</strong> comment with <a href="https://example.com">a link</a></p>' },
    }
  );
  expect(comment.status(), await comment.text()).toBe(201);
  const reports = watch(page);

  await page.goto(`/${slug}/browse/${seed.project.identifier}-${workItem.sequence_id}/`);
  await expect(page.getByText("comment with").first()).toBeVisible();

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("a sticky renders and edits with Trusted Types enforced", async ({ page, context, baseURL }) => {
  await signIn(page, baseURL!);
  const csrf = await (await context.request.get("/auth/get-csrf-token/")).json();
  const sticky = await context.request.post(`/api/workspaces/${slug}/stickies/`, {
    headers: { "X-CSRFToken": csrf.csrf_token, Referer: `${baseURL}/` },
    data: {
      name: "Trusted Types: sticky",
      description_html:
        '<p>sticky <strong>note</strong> <span data-text-color="gray">gray</span></p><ul><li><p>item</p></li></ul>',
    },
  });
  expect(sticky.status(), await sticky.text()).toBe(201);
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

test("the workspace home renders with Trusted Types enforced", async ({ page, baseURL }) => {
  await signIn(page, baseURL!);
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
