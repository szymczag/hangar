/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const MAX_CODE_POINT = 0x10ffff;

/**
 * Turns a callout's `data-emoji-unicode` attribute, the emoji's code points as
 * dash-separated decimals ("128161", "9757-65039"), back into the emoji.
 *
 * The callout extension config runs in the live server, so this stays a plain
 * function here instead of the `stringToEmoji` of `@plane/blocks`, whose entry
 * pulls in the picker's icon set and with it React components the server image
 * does not install. It validates the same way: a part that is not a code point
 * (not finite, below 0, above U+10FFFF) is dropped, and a value that still
 * cannot be converted gives an empty string. Empty parts are dropped too,
 * where blocks would turn them into U+0000.
 */
export function calloutEmojiFromUnicode(value: string | null | undefined): string {
  if (!value) return "";
  const codePoints = value
    .split("-")
    .map((part) => part.trim())
    .filter((part) => part !== "")
    .map(Number)
    .filter((n) => Number.isFinite(n) && n >= 0 && n <= MAX_CODE_POINT);
  try {
    return String.fromCodePoint(...codePoints);
  } catch {
    return "";
  }
}
