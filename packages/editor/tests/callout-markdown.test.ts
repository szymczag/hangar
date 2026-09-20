/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MarkdownSerializerState } from "@tiptap/pm/markdown";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { describe, expect, it } from "vitest";

import { CustomCalloutExtensionConfig } from "../src/core/extensions/callout/extension-config";

/** Records what the serializer writes, without a real document. */
function serialize(attrs: Record<string, unknown>): string {
  const written: string[] = [];
  const state = {
    write: (text: string) => written.push(text),
    wrapBlock: (_prefix: string, _empty: null, _node: unknown, render: () => void) => render(),
    renderContent: () => written.push("content\n"),
    closeBlock: () => undefined,
  } as unknown as MarkdownSerializerState;
  const storage = CustomCalloutExtensionConfig.config.addStorage?.call({} as never) as {
    markdown: { serialize(state: MarkdownSerializerState, node: ProseMirrorNode): void };
  };
  storage.markdown.serialize(state, { attrs } as unknown as ProseMirrorNode);
  return written.join("");
}

describe("a callout exported as markdown", () => {
  it("writes the emoji itself, never an image on another host", () => {
    const markdown = serialize({
      "data-logo-in-use": "emoji",
      "data-emoji-unicode": "128161",
      // Stored by older versions, and by the picker: it must not be exported.
      "data-emoji-url": "https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/1f4a1.png",
    });
    expect(markdown).toContain("> 💡");
    expect(markdown).not.toContain("http");
    expect(markdown).not.toContain("<img");
  });

  it("writes the icon name when an icon is in use", () => {
    expect(serialize({ "data-logo-in-use": "icon", "data-icon-name": "Info" })).toContain("<icon>Info icon</icon>");
  });
});
