/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import emojiRegex from "emoji-regex";

const MAX_CODE_POINT = 0x10ffff;
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
 */
export function calloutEmojiFromUnicode(value: string | null | undefined): string {
  if (!value) return "";
  const parts = value.split("-");
  if (!parts.every((part) => DECIMAL.test(part))) return "";
  const codePoints = parts.map(Number);
  if (!codePoints.every((n) => Number.isSafeInteger(n) && n <= MAX_CODE_POINT)) return "";
  const text = String.fromCodePoint(...codePoints);
  return SINGLE_EMOJI.test(text) ? text : "";
}

/** A callout icon name as the markdown export may write it: a plain identifier, or nothing. */
export function calloutIconName(value: unknown): string {
  return typeof value === "string" && ICON_NAME.test(value) ? value : "";
}
