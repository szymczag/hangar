/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { shortcodeToEmoji } from "@tiptap/extension-emoji";
import { describe, expect, it } from "vitest";

import { EDITOR_EMOJIS } from "../src/extensions/emoji/emoji-data";
import { emojiFromName, emojiName } from "../src/extensions/emoji/emoji-name";

describe("emojiFromName", () => {
  it.each([
    ["rocket", "🚀"],
    ["+1", "👍"],
    ["thumbsup", "👍"],
    ["100", "💯"],
    ["white_check_mark", "✅"],
    ["regional_indicator_p", "🇵"],
    ["family_man_woman_girl", "👨‍👩‍👧"],
  ])("resolves %s", (name, emoji) => {
    expect(emojiFromName(name)).toBe(emoji);
  });

  it("gives what the editor's own lookup gives for every name and shortcode in the set", () => {
    for (const item of EDITOR_EMOJIS) {
      for (const key of [item.name, ...item.shortcodes]) {
        const expected = shortcodeToEmoji(key, EDITOR_EMOJIS)?.emoji;
        expect(expected).toBeTruthy();
        expect(emojiFromName(key)).toBe(expected);
      }
    }
  });

  it("keeps no fallback image, so nothing loads from a CDN", () => {
    expect(EDITOR_EMOJIS.length).toBeGreaterThan(1000);
    expect(EDITOR_EMOJIS.every((item) => item.emoji && !("fallbackImage" in item))).toBe(true);
  });

  it.each([
    "not_an_emoji_name",
    "128640",
    "🚀",
    ":rocket:",
    "rocket ",
    "rocket\nsmile",
    "<script>",
    "",
    "a".repeat(65),
    "a".repeat(1_000_000),
    "constructor",
    "__proto__",
    "toString",
  ])("gives an empty string for %j", (name) => {
    expect(emojiFromName(name)).toBe("");
  });

  it.each([128640, null, undefined, true, {}, ["rocket"], { name: "rocket" }])(
    "gives an empty string for the non-string value %j",
    (value) => {
      expect(emojiFromName(value)).toBe("");
    }
  );
});

describe("emojiName", () => {
  it.each(["rocket", "+1", "not_an_emoji_name", "a".repeat(64)])("keeps the shortcode %s", (name) => {
    expect(emojiName(name)).toBe(name);
  });

  it.each(["128640", "100", "rocket\n", "<b>", "🚀", "", "a".repeat(65), 1, null, {}])("drops %j", (value) => {
    expect(emojiName(value)).toBe("");
  });
});
