/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Locator, Page, WebSocketRoute } from "@playwright/test";
import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The page editor's menus and popovers: the bubble menu and its dropdowns, the
 * link popovers, the slash command menu, the block menu, the table column
 * menu, the image toolbar and viewer, the code block's copy button, the
 * callout colour picker, and the mention and emoji suggestions. Then the
 * comment editor on a published board (apps/space).
 *
 * These are the 1.4 menus (Headless UI, floating-ui, lucide and the 1.4 Propel
 * icons) as they render before the editor moves to Propel (FORK.md ledger,
 * the editor stage); none of them showed in any story before.
 *
 * They all open the admin's private "Editor menus" page, which the seed fills
 * with every node the menus act on and no other story shows: the light user's
 * pages list never lists another user's private page. Selecting, hovering and
 * opening a menu leave the document alone, but the slash, mention and emoji
 * stories type a trigger character, and the editor sends every change to live,
 * which stores it. The write guard only sees `/api/` requests, so each story
 * here relays the live connection itself and drops the client's document
 * updates (Yjs sync step 2 and update messages); live still sends the document
 * and the session works, but nothing a story does reaches the stored page, in
 * a retry, in the soak, or in a parallel story.
 */

/** Read one lib0 unsigned varint from `bytes` at `cursor.offset`. */
function readVarUint(bytes: Buffer, cursor: { offset: number }): number | undefined {
  let value = 0;
  let multiplier = 1;
  while (cursor.offset < bytes.length) {
    const byte = bytes[cursor.offset++];
    value += (byte & 0x7f) * multiplier;
    if (byte < 0x80) return value;
    multiplier *= 0x80;
  }
  return undefined;
}

/**
 * A Hocuspocus message that would change the stored document: the document
 * name (a lib0 varstring), message type 0 (sync), then sync step 2 (1) or an
 * update (2). Awareness, auth and sync step 1 pass.
 */
function isDocumentWrite(message: string | Buffer): boolean {
  if (typeof message === "string") return false;
  const cursor = { offset: 0 };
  const nameLength = readVarUint(message, cursor);
  if (nameLength === undefined) return false;
  cursor.offset += nameLength;
  if (readVarUint(message, cursor) !== 0) return false;
  const step = readVarUint(message, cursor);
  return step === 1 || step === 2;
}

async function withoutDocumentWrites(page: Page): Promise<void> {
  await page.routeWebSocket(/\/live\//, (client: WebSocketRoute) => {
    const server = client.connectToServer();
    client.onMessage((message) => {
      if (!isDocumentWrite(message)) server.send(message);
    });
    server.onMessage((message) => client.send(message));
    client.onClose((code, reason) => server.close({ ...(code === undefined ? {} : { code }), reason: reason ?? "" }));
    server.onClose((code, reason) => client.close({ ...(code === undefined ? {} : { code }), reason: reason ?? "" }));
  });
}

async function openMenusPage(page: Page): Promise<{ main: Locator; editor: Locator }> {
  const seed = fixtures();
  await withoutDocumentWrites(page);
  await page.goto(`/${seed.workspace.slug}/projects/${seed.project.id}/pages/${seed.editorMenusPage.id}`);
  const main = page.getByRole("main").last();
  const editor = main.locator(".ProseMirror", { hasText: seed.editorMenusPage.lastParagraph }).first();
  // Editable only once the collaborative session has synced; a menu opened
  // before then shows its read-only form, or nothing.
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await page.mouse.move(0, 0);
  return { main, editor };
}

/** Select the seeded sentence with the keyboard, which shows the bubble menu without a drag. */
async function selectSentence(page: Page, editor: Locator): Promise<Locator> {
  const seed = fixtures();
  await editor.getByText(seed.editorMenusPage.selection, { exact: true }).click();
  await page.keyboard.press("End");
  await page.keyboard.press("Shift+Home");
  await page.mouse.move(0, 0);
  const menu = page.locator(".horizontal-scrollbar").filter({ hasText: "Color" }).last();
  await expect(menu).toBeVisible();
  return menu;
}

/** Put the caret in the empty paragraph that ends the page, for the typing stories. */
async function caretInEmptyParagraph(editor: Locator): Promise<void> {
  await editor.locator("p").last().click();
}

test("the bubble menu on a selection", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);
  const menu = await selectSentence(page, editor);

  await capture(page, "editor-bubble-menu", { ready: menu.getByText("Color"), target: menu });
});

test("the bubble menu's block type dropdown", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);
  const menu = await selectSentence(page, editor);

  await menu.getByRole("button", { name: "Text", exact: true }).click();
  const dropdown = page.getByRole("dialog").filter({ hasText: "Heading 1" }).last();
  await page.mouse.move(0, 0);

  await capture(page, "editor-bubble-menu-node-dropdown", { ready: dropdown.getByText("Heading 1"), target: dropdown });
});

test("the bubble menu's colour dropdown", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);
  const menu = await selectSentence(page, editor);

  await menu.getByRole("button", { name: "Color" }).click();
  const dropdown = page.getByRole("dialog").filter({ hasText: "Background colors" }).last();
  await page.mouse.move(0, 0);

  await capture(page, "editor-bubble-menu-color-dropdown", {
    ready: dropdown.getByText("Background colors"),
    target: dropdown,
  });
});

test("the link preview and link edit popovers", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const { editor } = await openMenusPage(page);

  await editor.getByRole("link", { name: seed.editorMenusPage.link }).hover();
  const preview = page.locator("div.shadow-md", { hasText: seed.editorMenusPage.linkHref }).last();
  await capture(page, "editor-link-preview", {
    ready: preview.getByText(seed.editorMenusPage.linkHref),
    target: preview,
  });

  // Copy, edit, remove: the second button switches the popover to its form.
  await preview.getByRole("button").nth(1).click();
  const form = page
    .locator("div.shadow-md")
    .filter({ has: page.getByPlaceholder("Enter or paste URL") })
    .last();
  await expect(form.getByPlaceholder("Enter or paste URL")).toHaveValue(seed.editorMenusPage.linkHref);
  await capture(page, "editor-link-edit", { ready: form.getByText("URL", { exact: true }), target: form });
});

test("the slash command menu", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);

  await caretInEmptyParagraph(editor);
  await page.keyboard.type("/");
  const menu = page.locator("#slash-command");
  await page.mouse.move(0, 0);

  await capture(page, "editor-slash-command-menu", { ready: menu.getByText("Text", { exact: true }), target: menu });
});

test("the block menu from the drag handle", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const { editor } = await openMenusPage(page);

  await editor.getByText(seed.editorMenusPage.selection, { exact: true }).hover();
  const handle = page.locator("#drag-handle");
  await expect(handle).toBeVisible();
  await handle.click();
  const menu = page.locator('[class*="min-w-[7rem]"]').filter({ hasText: "Duplicate" }).last();
  // The menu scales in; its finished state is a class, not a sleep.
  await expect(menu).toHaveClass(/opacity-100/);
  await page.mouse.move(0, 0);

  await capture(page, "editor-block-menu", { ready: menu.getByText("Delete"), target: menu });
});

test("the table column menu and its colour submenu", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);

  // The column handles act on the table the selection is in.
  const header = editor.locator("th", { hasText: "Owner" });
  await header.click();
  await header.locator(".table-col-handle-container button").click();
  const menu = page.locator('[class*="w-[12rem]"]').filter({ hasText: "Header column" }).last();
  await page.mouse.move(0, 0);
  await capture(page, "editor-table-column-menu", { ready: menu.getByText("Insert left"), target: menu });

  await menu.getByRole("button", { name: "Color" }).click();
  await page.mouse.move(0, 0);
  await capture(page, "editor-table-column-menu-color", {
    ready: menu.getByText("Background colors"),
    target: menu,
  });
});

test("the image toolbar and its alignment dropdown", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);

  const block = editor.locator(".group\\/image-component").first();
  // The image itself, served from object storage through the asset endpoint.
  const image = block.locator("img").first();
  await expect(image).toBeVisible();
  await block.hover();
  const fullScreen = block.getByRole("button", { name: "View image in full screen" });
  await expect(fullScreen).toBeVisible();
  await capture(page, "editor-image-toolbar", { ready: fullScreen, target: block });

  // The alignment dropdown: the toolbar's only trigger that is neither a link nor the viewer.
  await block
    .getByRole("button")
    .filter({ has: page.locator("svg.lucide-align-left") })
    .first()
    .click();
  await expect(block.locator("svg.lucide-align-center")).toBeVisible();
  await capture(page, "editor-image-toolbar-alignment", {
    ready: block.locator("svg.lucide-align-right"),
    target: block,
  });
});

test("the full-screen image viewer", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);

  const block = editor.locator(".group\\/image-component").first();
  await expect(block.locator("img").first()).toBeVisible();
  await block.hover();
  await block.getByRole("button", { name: "View image in full screen" }).click();
  const viewer = page.getByRole("dialog", { name: "Fullscreen image viewer" });
  await expect(viewer).toHaveCSS("opacity", "1");
  await page.mouse.move(0, 0);

  await capture(page, "editor-image-viewer", {
    ready: viewer.getByRole("button", { name: "Zoom in" }),
    target: viewer,
  });
});

test("the code block's copy button on hover", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const { editor } = await openMenusPage(page);

  const block = editor.locator(".code-block", { hasText: seed.editorMenusPage.code }).first();
  await block.locator("pre").hover();
  const copy = block.locator("button").first();
  await expect(copy).toBeVisible();

  await capture(page, "editor-code-block-copy", { ready: copy, target: block });
});

test("the callout colour picker", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const { editor } = await openMenusPage(page);

  const callout = editor.locator(".editor-callout-component", { hasText: seed.editorMenusPage.callout }).first();
  await callout.hover();
  await callout.getByRole("button", { name: "Color" }).click();
  const picker = callout.locator("section").last();
  await page.mouse.move(0, 0);

  await capture(page, "editor-callout-color-picker", { ready: picker.locator("button").first(), target: picker });
});

test("the mention suggestions", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);

  await caretInEmptyParagraph(editor);
  await page.keyboard.type("@");
  const menu = page.locator('[class*="w-[14rem]"]').filter({ hasText: "VR Light" }).last();
  await page.mouse.move(0, 0);

  await capture(page, "editor-mention-suggestions", { ready: menu.getByText("VR Light"), target: menu });
});

test("the emoji suggestions", async ({ asUser }) => {
  const page = await asUser("admin");
  const { editor } = await openMenusPage(page);

  await caretInEmptyParagraph(editor);
  await page.keyboard.type(":");
  const menu = page
    .locator("div")
    .filter({ has: page.locator("#emoji-item-4") })
    .last();
  await page.mouse.move(0, 0);

  await capture(page, "editor-emoji-suggestions", { ready: menu.locator("#emoji-item-4"), target: menu });
});

/**
 * The comment editor and its toolbar under a published board's work item, as
 * a signed-in reader sees it. Space renders the same editor package; nothing
 * is typed.
 */
test("the comment editor on a published board", async ({ asUser }) => {
  const page = await asUser("light");
  const seed = fixtures();
  await page.goto(`/spaces/issues/${seed.publishedBoard.anchor}/?peekId=${seed.publishedBoard.peekId}`);
  const section = page.locator(".issue-comments-section").first();
  const editor = section.locator(".ProseMirror").first();
  await expect(editor).toHaveAttribute("contenteditable", "true");
  await page.mouse.move(0, 0);

  await capture(page, "space-comment-editor", { ready: section.getByRole("button").first(), target: section });
});
