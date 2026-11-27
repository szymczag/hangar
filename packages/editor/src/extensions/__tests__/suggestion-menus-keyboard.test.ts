/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Extension } from "@tiptap/core";
import type { AnyExtension } from "@tiptap/core";
import { Editor, EditorContent } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EmojiExtension } from "@/extensions/emoji/extension";
import { CustomMentionExtension } from "@/extensions/mentions";
import { SlashCommands } from "@/extensions/slash-commands/root";
import type { TMentionSection } from "@/types";

// The slash, mention and emoji lists, driven the way a user drives them: text typed into a mounted
// editor opens the list through @tiptap/suggestion, and keys reach it through ProseMirror's keydown
// handler on the editor's DOM.

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// The utility extension's storage and dropbar bookkeeping, without its file plugins.
const DropbarStub = Extension.create({
  name: "utility",
  addStorage() {
    return { isTouchDevice: false };
  },
  addCommands() {
    return {
      addActiveDropbarExtension: () => () => true,
      removeActiveDropbarExtension: () => () => true,
    } as never;
  },
});

let root: Root | undefined;
let host: HTMLElement | undefined;
let editor: Editor | undefined;

const mount = async (extensions: AnyExtension[]) => {
  host = document.createElement("div");
  document.body.appendChild(host);
  editor = new Editor({ extensions: [StarterKit, DropbarStub, ...extensions], content: "<p></p>" });
  root = createRoot(host);
  await act(async () => {
    root?.render(createElement(EditorContent, { editor: editor! }));
  });
  return editor;
};

const type = async (text: string) => {
  await act(async () => {
    editor!.chain().focus("end").insertContent(text).run();
  });
};

const press = async (key: string) => {
  const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
  await act(async () => {
    editor!.view.dom.dispatchEvent(event);
  });
  return event;
};

const highlighted = (selector: string) =>
  [...document.querySelectorAll(`${selector} [data-highlighted]`)].map((row) => row.textContent);

const slashMenu = () => document.querySelector("#slash-command");
const emojiRows = () => [...document.querySelectorAll<HTMLButtonElement>("[id^='emoji-item-']")];
const mentionRows = () => [...document.querySelectorAll<HTMLButtonElement>("[id^='mention-item-']")];

afterEach(async () => {
  await act(async () => root?.unmount());
  editor?.destroy();
  host?.remove();
  document.body.innerHTML = "";
  root = undefined;
  host = undefined;
  editor = undefined;
  vi.useRealTimers();
});

describe("slash command menu", () => {
  it("opens on '/', moves with the arrow keys, wraps, and runs the highlighted command on Enter", async () => {
    await mount([SlashCommands({ disabledExtensions: [], flaggedExtensions: [] })]);
    await type("/");
    expect(slashMenu()).not.toBeNull();
    expect(highlighted("#slash-command")).toEqual(["Text"]);

    const down = await press("ArrowDown");
    expect(down.defaultPrevented).toBe(true);
    expect(highlighted("#slash-command")).toEqual(["Heading 1"]);

    await press("ArrowUp");
    await press("ArrowUp");
    // Up from the first row wraps to the last row of the last section.
    const rows = [...document.querySelectorAll("#slash-command button")];
    expect(highlighted("#slash-command")).toEqual([rows.at(-1)?.textContent]);

    await press("ArrowDown");
    await press("ArrowDown");
    expect(highlighted("#slash-command")).toEqual(["Heading 1"]);

    await press("Enter");
    expect(editor!.getJSON().content?.[0]).toMatchObject({ type: "heading", attrs: { level: 1 } });
    // the "/" query is consumed by the command
    expect(editor!.getText()).not.toContain("/");
    expect(slashMenu()).toBeNull();
  });

  it("narrows to the typed query and closes on Escape without running anything", async () => {
    await mount([SlashCommands({ disabledExtensions: [], flaggedExtensions: [] })]);
    await type("/quote");
    expect([...document.querySelectorAll("#slash-command button")].map((row) => row.textContent)).toEqual(["Quote"]);

    const escape = await press("Escape");
    expect(escape.defaultPrevented).toBe(true);
    expect(slashMenu()).toBeNull();
    expect(editor!.getText()).toBe("/quote");
    expect(editor!.getJSON().content?.[0]?.type).toBe("paragraph");
  });

  it("renders every row as a button, so a click or Enter on a focused row runs it", async () => {
    await mount([SlashCommands({ disabledExtensions: [], flaggedExtensions: [] })]);
    await type("/");
    const rows = [...document.querySelectorAll<HTMLButtonElement>("#slash-command button")];
    expect(rows.length).toBeGreaterThan(5);
    for (const row of rows) expect(row.getAttribute("type")).toBe("button");
  });
});

describe("emoji suggestion list", () => {
  it("lists matches for ':' plus a query, moves with the arrow keys and inserts on Enter", async () => {
    await mount([EmojiExtension]);
    await type(":smile");
    expect(emojiRows().length).toBeGreaterThan(1);
    expect(emojiRows()[0]?.hasAttribute("data-highlighted")).toBe(true);

    await press("ArrowDown");
    expect(emojiRows()[1]?.hasAttribute("data-highlighted")).toBe(true);
    await press("ArrowUp");
    await press("ArrowUp");
    expect(emojiRows().at(-1)?.hasAttribute("data-highlighted")).toBe(true);
    await press("ArrowDown");

    const first = emojiRows()[0]?.textContent ?? "";
    await press("Enter");
    const inserted = editor!.state.doc.firstChild?.firstChild;
    expect(inserted?.type.name).toBe("emoji");
    expect(first).toContain(`:${String(inserted?.attrs.name)}:`);
    expect(emojiRows()).toEqual([]);
  });

  it("closes on Escape and leaves the typed text", async () => {
    await mount([EmojiExtension]);
    await type(":smile");
    expect(emojiRows().length).toBeGreaterThan(0);

    // Escape used to throw: the close handler read the emoji storage from an editor it was not given.
    const escape = await press("Escape");
    expect(escape.defaultPrevented).toBe(true);
    expect(emojiRows()).toEqual([]);
    expect(editor!.getText()).toBe(":smile");
  });
});

describe("mention list", () => {
  const sections: TMentionSection[] = [
    {
      key: "users",
      title: "Users",
      items: [
        { id: "u1", entity_identifier: "u1", entity_name: "user_mention", title: "Ada", icon: null },
        { id: "u2", entity_identifier: "u2", entity_name: "user_mention", title: "Grace", icon: null },
      ],
    },
    {
      key: "more",
      title: "More users",
      items: [{ id: "u3", entity_identifier: "u3", entity_name: "user_mention", title: "Linus", icon: null }],
    },
  ];

  const mountMentions = async () => {
    const searchCallback = vi.fn(async () => sections);
    await mount([CustomMentionExtension({ searchCallback, renderComponent: () => null })]);
    await type("@");
    // the list searches after a 300ms debounce
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });
    return searchCallback;
  };

  it("shows the sections with their headings, moves across sections and selects on Enter", async () => {
    const searchCallback = await mountMentions();
    expect(searchCallback).toHaveBeenCalledWith("");
    expect(mentionRows().map((row) => row.textContent)).toEqual(["Ada", "Grace", "Linus"]);
    expect(document.body.textContent).toContain("More users");
    expect(mentionRows()[0]?.hasAttribute("data-highlighted")).toBe(true);

    await press("ArrowDown");
    await press("ArrowDown");
    expect(mentionRows()[2]?.hasAttribute("data-highlighted")).toBe(true);
    await press("ArrowDown");
    expect(mentionRows()[0]?.hasAttribute("data-highlighted")).toBe(true);
    await press("ArrowUp");
    expect(mentionRows()[2]?.hasAttribute("data-highlighted")).toBe(true);

    await press("Enter");
    const mention = editor!.getJSON().content?.[0]?.content?.[0];
    expect(mention).toMatchObject({ type: "mention", attrs: { entity_identifier: "u3" } });
    expect(mentionRows()).toEqual([]);
  });

  it("closes on Escape without inserting a mention", async () => {
    await mountMentions();
    expect(mentionRows().length).toBe(3);
    await press("Escape");
    expect(mentionRows()).toEqual([]);
    expect(editor!.getText()).toBe("@");
  });
});
