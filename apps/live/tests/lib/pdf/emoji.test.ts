/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createHash } from "crypto";
import { readFileSync } from "fs";
import { Font } from "@react-pdf/renderer";
import { describe, expect, it } from "vitest";
import { EMOJI_FONT_FAMILY, EMOJI_FONT_PATH, loadEmojiFont, splitEmoji, withEmojiFont } from "@/lib/pdf/emoji";

type ShapedGlyph = { id: number };
type LoadedFont = {
  postscriptName: string;
  hasGlyphForCodePoint: (codePoint: number) => boolean;
  layout: (text: string) => { glyphs: ShapedGlyph[] };
};

const loadedFont = async (fontStyle: "normal" | "italic" = "normal"): Promise<LoadedFont> => {
  await loadEmojiFont();
  return Font.getFont({ fontFamily: EMOJI_FONT_FAMILY, fontWeight: 400, fontStyle }).data as unknown as LoadedFont;
};

describe("bundled emoji font", () => {
  it("is the recorded Noto Emoji release", () => {
    // google/fonts ofl/notoemoji/NotoEmoji[wght].ttf, see assets/fonts/noto-emoji/README.md
    const sha256 = createHash("sha256").update(readFileSync(EMOJI_FONT_PATH)).digest("hex");
    expect(sha256).toBe("de6c18832938afc99caf132b39d6a30a19bac7f2e812e28db2535b4608d27551");
  });

  it.each([
    ["a face", "😊"],
    ["a skin tone", "👍🏽"],
    ["a ZWJ family", "👨‍👩‍👧"],
    ["a text-default emoji with VS16", "☝️"],
    ["a keycap", "1️⃣"],
    ["a flag", "🇵🇱"],
  ])("shapes %s into one real glyph, not the missing glyph", async (_label, emoji) => {
    const { glyphs } = (await loadedFont()).layout(emoji);
    expect(glyphs).toHaveLength(1);
    expect(glyphs[0].id).not.toBe(0);
  });

  it("is registered for italic text too", async () => {
    expect((await loadedFont("italic")).postscriptName).toBe("NotoEmoji-Regular");
  });

  it("claims surrogate code units, so react-pdf keeps both halves of a pair in it", async () => {
    const font = await loadedFont();
    expect(font.hasGlyphForCodePoint(0xd83d)).toBe(true);
    expect(font.hasGlyphForCodePoint(0xde0a)).toBe(true);
    expect(font.hasGlyphForCodePoint(0x1f60a)).toBe(true);
    // letters stay with the page font
    expect(font.hasGlyphForCodePoint(0x41)).toBe(false);
  });

  it("wraps the lookup once however often it loads", async () => {
    await loadEmojiFont();
    const font = await loadedFont();
    const lookup = font.hasGlyphForCodePoint;
    await loadEmojiFont();
    expect(font.hasGlyphForCodePoint).toBe(lookup);
  });
});

describe("splitEmoji", () => {
  it("returns text without emoji as one plain part", () => {
    expect(splitEmoji("Plain 123 #*")).toEqual([{ text: "Plain 123 #*", start: 0, emoji: false }]);
  });

  it("keeps each sequence whole and the text between them", () => {
    expect(splitEmoji("a👨‍👩‍👧b 1️⃣👍🏽")).toEqual([
      { text: "a", start: 0, emoji: false },
      { text: "👨‍👩‍👧", start: 1, emoji: true },
      { text: "b ", start: 9, emoji: false },
      { text: "1️⃣", start: 11, emoji: true },
      { text: "👍🏽", start: 14, emoji: true },
    ]);
  });

  it("is empty for an empty string", () => {
    expect(splitEmoji("")).toEqual([]);
  });
});

describe("withEmojiFont", () => {
  it("returns text without emoji unchanged", () => {
    expect(withEmojiFont("Hello")).toBe("Hello");
  });

  it("sets only the emoji in the emoji font", () => {
    const parts = withEmojiFont("Hi 😊!");
    expect(Array.isArray(parts)).toBe(true);
    const [before, emoji, after] = parts as [string, { props: { style: unknown; children: string } }, string];
    expect(before).toBe("Hi ");
    expect(emoji.props).toMatchObject({ style: { fontFamily: EMOJI_FONT_FAMILY }, children: "😊" });
    expect(after).toBe("!");
  });
});
