/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Editor, EditorContent } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { act, createElement, createRef } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { LinkViewContainer } from "@/components/editors/link-view-container";
import { BubbleMenuLinkSelector } from "@/components/menus/bubble-menu/link-selector";
import { CustomLinkExtension } from "@/extensions/custom-link";

// The link selector in the bubble menu, the link preview shown on hover and its edit view, mounted
// against a real editor.

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const DANGEROUS_HREFS = [
  "javascript:alert(1)",
  "JavaScript:alert(document.domain)",
  "java\tscript:alert(1)",
  "\u0001javascript:alert(1)",
  "  javascript:alert(1)",
  "data:text/html,<script>alert(1)</script>",
  "vbscript:msgbox(1)",
];

let root: Root | undefined;
let host: HTMLElement | undefined;
let editor: Editor | undefined;

const createEditor = (content: string) => {
  editor = new Editor({ extensions: [StarterKit.configure({ link: false }), CustomLinkExtension], content });
  return editor;
};

const render = async (element: ReturnType<typeof createElement>) => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root?.render(element));
};

const setInputValue = async (input: HTMLInputElement, value: string) => {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
};

const pressEnter = async (target: Element) => {
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
  });
};

const click = async (target: Element) => {
  await act(async () => {
    target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
};

const linkMarks = () => {
  const marks: { href: string; text: string }[] = [];
  editor!.state.doc.descendants((node) => {
    const link = node.marks.find((mark) => mark.type.name === "link");
    if (link) marks.push({ href: String(link.attrs.href), text: node.text ?? "" });
  });
  return marks;
};

const button = (name: string) =>
  [...document.querySelectorAll("button")].find(
    (candidate) => candidate.getAttribute("aria-label") === name || candidate.textContent?.trim() === name
  );

afterEach(async () => {
  await act(async () => root?.unmount());
  editor?.destroy();
  host?.remove();
  document.body.innerHTML = "";
  root = undefined;
  host = undefined;
  editor = undefined;
});

describe("bubble menu link selector", () => {
  const openSelector = async () => {
    createEditor("<p>hello world</p>");
    editor!.commands.setTextSelection({ from: 1, to: 6 });
    await render(createElement(BubbleMenuLinkSelector, { editor: editor! }));
    const trigger = button("Link");
    expect(trigger).toBeDefined();
    await click(trigger!);
    const input = document.querySelector<HTMLInputElement>("input[aria-label='Link URL']");
    expect(input).not.toBeNull();
    return input!;
  };

  it.each(DANGEROUS_HREFS)("saves nothing for %j", async (href) => {
    const input = await openSelector();
    input.value = href;
    await pressEnter(input);

    expect(linkMarks()).toEqual([]);
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(document.body.textContent).toContain("Please enter a valid URL");

    await click(button("Apply link")!);
    expect(linkMarks()).toEqual([]);
  });

  it("links the selection for an ordinary address", async () => {
    const input = await openSelector();
    input.value = "example.com/docs";
    await pressEnter(input);

    expect(linkMarks()).toEqual([{ href: "https://example.com/docs", text: "hello" }]);
    expect(document.querySelector("input[aria-label='Link URL']")).toBeNull();
  });
});

describe("link preview on hover", () => {
  const hoverLink = async () => {
    createEditor('<p>see <a href="https://example.com/a">the docs</a> here</p>');
    const containerRef = createRef<HTMLDivElement>();
    await render(
      createElement(
        "div",
        { ref: containerRef },
        createElement(EditorContent, { editor: editor! }),
        createElement(LinkViewContainer, { editor: editor!, containerRef })
      )
    );
    const anchor = editor!.view.dom.querySelector("a");
    expect(anchor).not.toBeNull();
    await act(async () => {
      anchor!.dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
    });
    return anchor!;
  };

  it("opens the preview without writing event-handler attributes onto the link", async () => {
    const anchor = await hoverLink();

    expect(button("Copy link")).toBeDefined();
    expect(document.body.textContent).toContain("https://example.com/a");
    const handlerAttributes = anchor.getAttributeNames().filter((name) => name.toLowerCase().startsWith("on"));
    expect(handlerAttributes).toEqual([]);
    expect(document.querySelectorAll("[onpointerdown], [onkeydown], [onmousedown], [onclick]")).toHaveLength(0);
    // the editor's fixed target and rel are what reaches the DOM
    expect(anchor.getAttribute("target")).toBe("_blank");
    expect(anchor.getAttribute("rel")).toBe("noopener noreferrer nofollow");
  });

  it.each(DANGEROUS_HREFS)("keeps the link's address when the edit view is given %j", async (href) => {
    await hoverLink();
    await click(button("Edit link")!);
    const [urlInput] = [...document.querySelectorAll<HTMLInputElement>("input")];
    expect(urlInput?.value).toBe("https://example.com/a");

    await setInputValue(urlInput!, href);
    expect(urlInput!.value).toBe(href);
    await pressEnter(urlInput!);

    expect(linkMarks()).toEqual([{ href: "https://example.com/a", text: "the docs" }]);
  });

  it("changes the link's address in the edit view for an ordinary address", async () => {
    await hoverLink();
    await click(button("Edit link")!);
    const [urlInput] = [...document.querySelectorAll<HTMLInputElement>("input")];
    await setInputValue(urlInput!, "https://example.org/b");
    await pressEnter(urlInput!);

    expect(linkMarks()).toEqual([{ href: "https://example.org/b", text: "the docs" }]);
  });
});
