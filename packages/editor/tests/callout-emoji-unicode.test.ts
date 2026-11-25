/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { calloutEmojiFromUnicode } from "../src/extensions/callout/emoji-unicode";

describe("calloutEmojiFromUnicode", () => {
  it("turns one code point into its emoji", () => {
    expect(calloutEmojiFromUnicode("128161")).toBe("💡");
  });

  it("joins dash-separated code points, as the picker stores sequences", () => {
    // U+261D WHITE UP POINTING INDEX + U+FE0F VARIATION SELECTOR-16
    expect(calloutEmojiFromUnicode("9757-65039")).toBe("☝️");
    // family: man, ZWJ, woman, ZWJ, girl
    expect(calloutEmojiFromUnicode("128104-8205-128105-8205-128103")).toBe("👨‍👩‍👧");
  });

  it("gives an empty string for no value", () => {
    expect(calloutEmojiFromUnicode("")).toBe("");
    expect(calloutEmojiFromUnicode(undefined)).toBe("");
    expect(calloutEmojiFromUnicode(null)).toBe("");
  });

  it("drops parts that are not code points", () => {
    expect(calloutEmojiFromUnicode("abc")).toBe("");
    expect(calloutEmojiFromUnicode("1114112")).toBe("");
    expect(calloutEmojiFromUnicode("Infinity")).toBe("");
    expect(calloutEmojiFromUnicode("128161-x-1114112")).toBe("💡");
  });

  it("drops empty parts instead of writing U+0000", () => {
    expect(calloutEmojiFromUnicode("128161-")).toBe("💡");
    expect(calloutEmojiFromUnicode("-128161")).toBe("💡");
    expect(calloutEmojiFromUnicode(" 128161 ")).toBe("💡");
  });

  it("gives an empty string when a part is in range but not an integer", () => {
    expect(calloutEmojiFromUnicode("128161.5")).toBe("");
  });

  it("never produces markup or a URL from a crafted value", () => {
    expect(calloutEmojiFromUnicode("<img src=x>")).toBe("");
    expect(calloutEmojiFromUnicode("https://example.com/a.png")).toBe("");
  });
});
