/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createRequire } from "module";
import { Font, Text } from "@react-pdf/renderer";
import type { ReactElement } from "react";

/**
 * The emoji font the export embeds: Noto Emoji, Google's monochrome emoji font
 * (SIL OFL 1.1), vendored under `apps/live/assets/fonts/noto-emoji` with its
 * licence and provenance. It is read from disk, so an export never fetches
 * anything; react-pdf's `Font.registerEmojiSource` would download an image per
 * emoji from a CDN instead.
 */
export const EMOJI_FONT_FAMILY = "Noto Emoji";

const require = createRequire(import.meta.url);

/** Absolute path of the bundled emoji font, resolved through the package's own `exports`. */
export const EMOJI_FONT_PATH = require.resolve("live/assets/fonts/noto-emoji/NotoEmoji-wght.ttf");

const EMOJI_FONT_STYLES = ["normal", "italic"] as const;

// The file is a variable font; react-pdf draws its default instance (weight
// 400). It is registered for both styles so bold and italic text resolve it.
Font.register({
  family: EMOJI_FONT_FAMILY,
  fonts: EMOJI_FONT_STYLES.map((fontStyle) => ({ src: EMOJI_FONT_PATH, fontWeight: 400, fontStyle })),
});

const isSurrogate = (codeUnit: number): boolean => codeUnit >= 0xd800 && codeUnit <= 0xdfff;

type GlyphLookup = { hasGlyphForCodePoint: (codePoint: number) => boolean };
const claimedSurrogates = new WeakSet<object>();

/**
 * Loads the emoji font and lets it take the halves of surrogate pairs.
 *
 * react-pdf (textkit 6) picks a font for each UTF-16 code unit, not each code
 * point, so it asks every font in the stack for a glyph for a lone surrogate.
 * None has one, and the character lands in the stack's last font, Helvetica,
 * which react-pdf always appends: every emoji above U+FFFF came out as two
 * broken WinAnsi bytes. Claiming surrogates puts both
 * halves of the pair in the emoji font, which then shapes the whole code point.
 * A non-emoji character above U+FFFF had no glyph in Helvetica either, so it
 * is still drawn as a missing glyph, now from this font.
 */
const claimSurrogates = async (fontStyle: (typeof EMOJI_FONT_STYLES)[number]): Promise<void> => {
  const descriptor = { fontFamily: EMOJI_FONT_FAMILY, fontWeight: 400, fontStyle };
  await Font.load(descriptor);
  const font = Font.getFont(descriptor).data as GlyphLookup | null;
  if (!font || claimedSurrogates.has(font)) return;
  const hasGlyph = font.hasGlyphForCodePoint.bind(font);
  font.hasGlyphForCodePoint = (codePoint) => isSurrogate(codePoint) || hasGlyph(codePoint);
  claimedSurrogates.add(font);
};

export const loadEmojiFont = async (): Promise<void> => {
  await Promise.all(EMOJI_FONT_STYLES.map(claimSurrogates));
};

/** Every RGI emoji, sequences included (skin tones, ZWJ families, keycaps, flags). */
const EMOJI_SEQUENCE = new RegExp(String.raw`\p{RGI_Emoji}`, "gv");

/** A run of `text`, starting at code unit `start`. */
export type EmojiTextPart = { text: string; start: number; emoji: boolean };

/** Splits `text` into runs of plain text and whole emoji sequences, in order. */
export const splitEmoji = (text: string): EmojiTextPart[] => {
  const parts: EmojiTextPart[] = [];
  let last = 0;
  for (const match of text.matchAll(EMOJI_SEQUENCE)) {
    const start = match.index;
    if (start > last) parts.push({ text: text.slice(last, start), start: last, emoji: false });
    parts.push({ text: match[0], start, emoji: true });
    last = start + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last), start: last, emoji: false });
  return parts;
};

/**
 * Text content with each emoji sequence set in the emoji font.
 *
 * The page font falls back to the emoji font character by character, which is
 * enough for a single emoji but can split a sequence: Inter has the digits, `#`,
 * `*`, `©` and `™`, so a keycap or `™️` would be drawn from Inter with a stray
 * variation selector from the emoji font. A whole sequence in its own span stays in one font, which joins it into one
 * glyph (`loadEmojiFont` must have run). Text without emoji is returned
 * unchanged.
 */
export const withEmojiFont = (text: string): string | (string | ReactElement)[] => {
  const parts = splitEmoji(text);
  if (!parts.some((part) => part.emoji)) return text;
  return parts.map((part) =>
    part.emoji ? (
      <Text key={part.start} style={{ fontFamily: EMOJI_FONT_FAMILY }}>
        {part.text}
      </Text>
    ) : (
      part.text
    )
  );
};
