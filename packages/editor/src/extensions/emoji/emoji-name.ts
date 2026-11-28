/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isSingleEmoji } from "@/extensions/callout/emoji-unicode";
// local imports
import { EDITOR_EMOJIS } from "./emoji-data";

// The emoji node stores one attribute, `name`, the emoji's name or one of its
// shortcodes ("rocket", "+1"), never the character itself. Every name and
// shortcode in the set uses these characters; the longest has 40.
const MAX_NAME_LENGTH = 64;
const EMOJI_NAME = /^[A-Za-z0-9_+-]+$/;
// "100" and "1234" are emoji names, but a bare number is also what a code point
// looks like, and one is never printed as a name.
const DIGITS = /^\d+$/;
// The set's 26 `regional_indicator_*` entries are single letters of a flag,
// which emoji-regex does not count as an emoji on their own.
const REGIONAL_INDICATOR = /^\p{Regional_Indicator}$/u;

let byName: Map<string, string> | undefined;

/**
 * Name and shortcode to character, built once. Keys keep their first item, so
 * a lookup gives what `shortcodeToEmoji(name, EDITOR_EMOJIS)`, which the
 * editor's `renderText` uses, gives.
 */
const emojiByName = (): Map<string, string> => {
  if (byName) return byName;
  const map = new Map<string, string>();
  for (const item of EDITOR_EMOJIS) {
    for (const key of [item.name, ...item.shortcodes]) {
      if (!map.has(key) && item.emoji) map.set(key, item.emoji);
    }
  }
  byName = map;
  return map;
};

/** Whether `value` is shaped like an emoji name: a short string of shortcode characters. */
const isEmojiName = (value: unknown): value is string =>
  typeof value === "string" && value.length <= MAX_NAME_LENGTH && EMOJI_NAME.test(value);

/**
 * An emoji node's `name` as it may be printed in place of its emoji: a plain
 * shortcode that is not a bare number, or nothing.
 */
export function emojiName(value: unknown): string {
  return isEmojiName(value) && !DIGITS.test(value) ? value : "";
}

/**
 * Turns an emoji node's `name` attribute into its character, from the
 * editor's own bundled emoji set, without any network access.
 *
 * The attribute is page content anyone who can edit the page controls, so it
 * is length-capped and limited to shortcode characters before the lookup, and
 * the result must be exactly one emoji (or one flag letter). A name that is not a string, is not a
 * shortcode or names no emoji in the set gives an empty string; nothing here
 * throws.
 */
export function emojiFromName(value: unknown): string {
  if (!isEmojiName(value)) return "";
  const emoji = emojiByName().get(value);
  return emoji && (isSingleEmoji(emoji) || REGIONAL_INDICATOR.test(emoji)) ? emoji : "";
}
