/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { EditorView } from "@tiptap/pm/view";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clickHandler } from "../src/core/extensions/custom-link/helpers/clickHandler";
import { isNavigableHref } from "../src/core/extensions/custom-link/url-security";
import { processAssetDuplication } from "../src/core/helpers/paste-asset";

type TFakeElement = {
  nodeName: string;
  parentNode?: TFakeElement;
  href?: string;
  getAttribute?: (name: string) => string | null;
};

/** `<div><a href=…><strong>text</strong></a></div>`, as the browser would resolve it. */
const linkWithChild = (rawHref: string, resolvedHref: string) => {
  const div: TFakeElement = { nodeName: "DIV" };
  const anchor: TFakeElement = {
    nodeName: "A",
    parentNode: div,
    href: resolvedHref,
    getAttribute: (name) => (name === "href" ? rawHref : null),
  };
  const strong: TFakeElement = { nodeName: "STRONG", parentNode: anchor };
  return strong;
};

const click = (target: TFakeElement) => {
  const plugin = clickHandler({ type: {} as never });
  const handleClick = plugin.props.handleClick as (view: EditorView, pos: number, event: MouseEvent) => boolean;
  return handleClick({} as EditorView, 0, { button: 0, target } as unknown as MouseEvent);
};

describe("link click handler", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens an http(s) link in a new context without an opener", () => {
    const open = vi.fn();
    vi.stubGlobal("window", { open });

    expect(click(linkWithChild("https://example.com/a", "https://example.com/a"))).toBe(true);
    expect(open).toHaveBeenCalledWith("https://example.com/a", "_blank", "noopener,noreferrer");
  });

  it("never opens a script URL, including through a child of the link", () => {
    const open = vi.fn();
    vi.stubGlobal("window", { open });

    expect(click(linkWithChild("java\tscript:alert(1)", "javascript:alert(1)"))).toBe(false);
    expect(click(linkWithChild("javascript:alert(1)", "javascript:alert(1)"))).toBe(false);
    expect(
      click(linkWithChild("data:text/html,<script>alert(1)</script>", "data:text/html,<script>alert(1)</script>"))
    ).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });

  it("does not open the current page for a link whose href was blanked", () => {
    const open = vi.fn();
    vi.stubGlobal("window", { open });

    expect(click(linkWithChild("", "https://app.example/current/page"))).toBe(false);
    expect(open).not.toHaveBeenCalled();
  });
});

describe("isNavigableHref", () => {
  it.each(["https://example.com", "http://example.com", "mailto:a@example.com", "tel:+48123"])("allows %s", (href) => {
    expect(isNavigableHref(href)).toBe(true);
  });

  it.each([
    "javascript:alert(1)",
    "java\tscript:alert(1)",
    "vbscript:x",
    "file:///etc/passwd",
    "ftp://x",
    "",
    "/relative",
  ])("refuses %j", (href) => {
    expect(isNavigableHref(href)).toBe(false);
  });
});

describe("paste asset duplication", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("parses clipboard HTML into an inert document, never a live-document element", () => {
    // An element from document.createElement belongs to the live document:
    // assigning `<img onerror>` to its innerHTML loads the image and runs the
    // handler even though it is never attached.
    const createElement = vi.fn();
    const parseFromString = vi.fn(() => ({ body: { querySelectorAll: () => [] } }));
    vi.stubGlobal("document", { createElement });
    vi.stubGlobal(
      "DOMParser",
      class {
        parseFromString = parseFromString;
      }
    );

    const html = "<img src=x onerror=alert(1)><p>pasted</p>";
    expect(processAssetDuplication(html).processedHtml).toBe(html);
    expect(parseFromString).toHaveBeenCalledWith(html, "text/html");
    expect(createElement).not.toHaveBeenCalled();
  });
});
