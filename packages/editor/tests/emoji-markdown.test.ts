/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { getSchema } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { StarterKit } from "@tiptap/starter-kit";
import { MarkdownSerializer, defaultMarkdownSerializer } from "prosemirror-markdown";
import type { MarkdownSerializerState } from "prosemirror-markdown";
import { describe, expect, it } from "vitest";

import { EDITOR_EMOJIS } from "../src/extensions/emoji/emoji-data";
import { EmojiExtensionConfig } from "../src/extensions/emoji/extension-config";

type TSerialize = (state: MarkdownSerializerState, node: ProseMirrorNode) => void;

const storage = EmojiExtensionConfig.config.addStorage?.call({
  parent: () => ({}),
  options: { emojis: EDITOR_EMOJIS },
} as never) as unknown as { markdown: { serialize: TSerialize } };

const schema = getSchema([StarterKit, EmojiExtensionConfig]);

/** The markdown export of a paragraph holding one emoji node between two words. */
function exportMarkdown(name: unknown): string {
  const doc = schema.node("doc", null, [
    schema.node("paragraph", null, [schema.text("Before "), schema.node("emoji", { name }), schema.text(" after")]),
  ]);
  const serializer = new MarkdownSerializer(
    { ...defaultMarkdownSerializer.nodes, emoji: storage.markdown.serialize },
    defaultMarkdownSerializer.marks
  );
  return serializer.serialize(doc);
}

describe("an emoji node exported as markdown", () => {
  it.each([
    ["rocket", "🚀"],
    ["+1", "👍"],
    ["100", "💯"],
  ])("writes the emoji for %s", (name, emoji) => {
    expect(exportMarkdown(name)).toBe(`Before ${emoji} after`);
  });

  it("writes an unknown shortcode back as :name:", () => {
    expect(exportMarkdown("not_an_emoji_name")).toBe("Before :not_an_emoji_name: after");
  });

  it.each([
    "x:\n\n![](https://evil.example/t.png)\n<img src=x onerror=alert(1)>",
    "<script>alert(1)</script>",
    "[link](javascript:alert(1))",
    "128640",
    "a".repeat(65),
    "",
    null,
  ])("writes nothing for the name %j", (name) => {
    expect(exportMarkdown(name)).toBe("Before  after");
  });
});
