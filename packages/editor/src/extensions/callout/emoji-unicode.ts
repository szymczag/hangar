/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import emojiRegex from "emoji-regex";

const MAX_CODE_POINT = 0x10ffff;
// The longest RGI emoji, a kiss or couple with two skin tones, has 10 code
// points; each part has at most 7 digits ("1114111") and a dash.
const MAX_PARTS = 16;
const MAX_STORED_LENGTH = MAX_PARTS * 8;
const DECIMAL = /^\d+$/;
const ICON_NAME = /^[A-Za-z0-9_-]+$/;

const emoji = emojiRegex();
/** Exactly one emoji, sequences included (skin tones, ZWJ families, keycaps, flags). */
const SINGLE_EMOJI = new RegExp(`^(?:${emoji.source})$`, emoji.flags.replace("g", ""));

/**
 * Turns a callout's `data-emoji-unicode` attribute, the emoji's code points as
 * dash-separated decimals ("128161", "9757-65039"), back into the emoji.
 *
 * The attribute is page content anyone who can edit the page controls, and the
 * markdown serializer writes the result unescaped. So every part must be plain
 * decimal digits (no hex, exponent, sign or blank) naming a code point, and the
 * result must be exactly one emoji; anything else gives an empty string. Without
 * that, code points for newlines, `<`, `!` or `[` would put a link, an image on
 * another host or raw HTML into the exported markdown.
 *
 * The callout extension config runs in the live server, so this stays here
 * instead of the `stringToEmoji` of `@plane/blocks`, whose entry pulls in the
 * picker's icon set and with it React components the server image does not
 * install.
 *
 * The attribute is not always a string: the editor's HTML parser turns a single
 * code point into a number, so a number is read as its decimal form and any
 * other type gives an empty string.
 */
export function calloutEmojiFromUnicode(value: unknown): string {
  // Parsed from HTML, a single code point ("128161") comes back as a number.
  const stored = typeof value === "number" ? String(value) : value;
  if (typeof stored !== "string" || !stored) return "";
  // Bounded before anything is split or spread: a value with some 200,000
  // parts passed every check below and then overflowed the call stack in
  // String.fromCodePoint, failing the whole export.
  if (stored.length > MAX_STORED_LENGTH) return "";
  const parts = stored.split("-");
  if (parts.length > MAX_PARTS || !parts.every((part) => DECIMAL.test(part))) return "";
  const codePoints = parts.map(Number);
  if (!codePoints.every((n) => Number.isSafeInteger(n) && n <= MAX_CODE_POINT)) return "";
  try {
    const text = String.fromCodePoint(...codePoints);
    return SINGLE_EMOJI.test(text) ? text : "";
  } catch {
    // Not reachable with the bounds above; page content must never fail a caller.
    return "";
  }
}

/** A callout icon name as the markdown export may write it: a plain identifier, or nothing. */
export function calloutIconName(value: unknown): string {
  return typeof value === "string" && ICON_NAME.test(value) ? value : "";
}
