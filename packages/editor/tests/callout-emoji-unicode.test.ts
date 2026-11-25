/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { calloutEmojiFromUnicode, calloutIconName } from "../src/extensions/callout/emoji-unicode";

/** The attribute as the picker stores it: each code point in decimal, dash-separated. */
const encode = (text: string): string => [...text].map((c) => c.codePointAt(0)).join("-");

describe("calloutEmojiFromUnicode", () => {
  it.each(["💡", "👍🏽", "👨‍👩‍👧", "1️⃣", "🇵🇱", "☝️"])("round-trips %s", (emoji) => {
    expect(calloutEmojiFromUnicode(encode(emoji))).toBe(emoji);
  });

  it("reads the stored form directly", () => {
    expect(calloutEmojiFromUnicode("128161")).toBe("💡");
    expect(calloutEmojiFromUnicode("9757-65039")).toBe("☝️");
  });

  it("gives an empty string for no value", () => {
    expect(calloutEmojiFromUnicode("")).toBe("");
    expect(calloutEmojiFromUnicode(undefined)).toBe("");
    expect(calloutEmojiFromUnicode(null)).toBe("");
  });

  it.each([
    "0x1F4A1",
    "1.28161e5",
    "1e5",
    "+128161",
    " 128161",
    "128161 ",
    "Infinity",
    "NaN",
    "abc",
    "-1",
    "128161-",
    "-128161",
    "128161--128161",
    "1114112",
    "99999999999999999999",
  ])("rejects the part form %j", (value) => {
    expect(calloutEmojiFromUnicode(value)).toBe("");
  });

  it.each([
    ["markdown and HTML injection", "\n\n![](https://evil.example/t.png)\n<img src=x onerror=alert(1)>"],
    ["an emoji followed by a new paragraph", "💡\n\n# heading"],
    ["an emoji followed by markup", "💡<img src=x>"],
    ["a link", "[x](https://evil.example)"],
    ["a URL", "https://evil.example/t.png"],
    ["a lone <", "<"],
    ["a lone !", "!"],
    ["a lone [", "["],
    ["a newline", "\n"],
    ["NUL", "\u0000"],
    ["ESC (C0)", "\u001b"],
    ["NEL (C1)", "\u0085"],
    ["CSI (C1)", "\u009b"],
    ["an emoji with a C1 control", "💡\u0085"],
    ["two emoji", "💡💡"],
    ["a digit", "1"],
    ["a letter", "a"],
  ])("gives an empty string for the code points of %s", (_label, text) => {
    expect(calloutEmojiFromUnicode(encode(text))).toBe("");
  });
});

describe("calloutIconName", () => {
  it.each(["Info", "AlertTriangle", "lightbulb_outline", "arrow-right", "Icon2"])("keeps %s", (name) => {
    expect(calloutIconName(name)).toBe(name);
  });

  it.each([
    "",
    "Info icon</icon>\n\n![](https://evil.example/t.png)",
    "<img src=x onerror=alert(1)>",
    "Info\nAlert",
    "Info icon",
    "[x](y)",
    undefined,
    null,
    42,
  ])("drops %j", (name) => {
    expect(calloutIconName(name)).toBe("");
  });
});
