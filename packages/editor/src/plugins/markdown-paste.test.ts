/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";
import { hasOnlyPlainWrappers, htmlAddsNoFormatting, looksLikeMarkdown } from "./markdown-paste";

describe("looksLikeMarkdown", () => {
  it("recognizes block constructs", () => {
    for (const text of [
      "# Heading\nbody",
      "### Heading\nbody",
      "```\ncode\n```",
      "- item\n- item",
      "* item\n* item",
      "1. one\n2. two",
      "> quoted text",
      "| a | b |\n| - | - |",
      "---\nbelow",
      "- [x] done\n- [ ] todo",
    ]) {
      expect(looksLikeMarkdown(text), text).toBe(true);
    }
  });

  it("recognizes inline constructs", () => {
    for (const text of [
      "some **bold** words",
      "some _italic_ words",
      "some `code` words",
      "some ~~struck~~ words",
      "a [link](https://example.com) here",
    ]) {
      expect(looksLikeMarkdown(text), text).toBe(true);
    }
  });

  it("leaves ordinary prose alone", () => {
    for (const text of [
      "just a sentence",
      "issue #42 needs review",
      "a * b = c",
      "5 - 3 = 2",
      "email me at someone@example.com",
      "C:\\Users\\maciek\\notes.txt",
      "snake_case and another_name in one line",
      "1.5 million rows",
      "",
      "   ",
    ]) {
      expect(looksLikeMarkdown(text), text).toBe(false);
    }
  });

  it("does not convert a single token, however marked up it looks", () => {
    expect(looksLikeMarkdown("**bold**")).toBe(false);
    expect(looksLikeMarkdown("#heading")).toBe(false);
    expect(looksLikeMarkdown("https://example.com/a_b_c")).toBe(false);
  });
});

describe("hasOnlyPlainWrappers", () => {
  it("accepts what a browser or plain editor wraps lines in", () => {
    expect(hasOnlyPlainWrappers(["DIV", "BR", "SPAN"])).toBe(true);
    expect(hasOnlyPlainWrappers(["HTML", "HEAD", "META", "BODY", "DIV"])).toBe(true);
    expect(hasOnlyPlainWrappers([])).toBe(true);
  });

  it("refuses formatting the HTML flavour already carries", () => {
    expect(hasOnlyPlainWrappers(["H2", "P"])).toBe(false);
    expect(hasOnlyPlainWrappers(["DIV", "STRONG"])).toBe(false);
    expect(hasOnlyPlainWrappers(["UL", "LI"])).toBe(false);
    expect(hasOnlyPlainWrappers(["DIV", "A"])).toBe(false);
    expect(hasOnlyPlainWrappers(["TABLE", "TR", "TD"])).toBe(false);
  });
});

describe("htmlAddsNoFormatting", () => {
  it("accepts a wrapper that only repeats the characters", () => {
    // textContent of <div># Heading</div><div>body</div> has no separator,
    // while the plain flavour has a newline.
    expect(htmlAddsNoFormatting("# Headingbody", "# Heading\nbody")).toBe(true);
    expect(htmlAddsNoFormatting("  # Heading   body  ", "# Heading body")).toBe(true);
  });

  it("refuses text the other flavour does not contain", () => {
    expect(htmlAddsNoFormatting("Heading body extra", "# Heading body")).toBe(false);
    expect(htmlAddsNoFormatting("something else", "# Heading")).toBe(false);
  });
});
