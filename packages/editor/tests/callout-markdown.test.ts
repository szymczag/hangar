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

import { CustomCalloutExtensionConfig } from "../src/extensions/callout/extension-config";

type TSerialize = (state: MarkdownSerializerState, node: ProseMirrorNode) => void;

const storage = CustomCalloutExtensionConfig.config.addStorage?.call({} as never) as {
  markdown: { serialize: TSerialize };
};

const schema = getSchema([StarterKit, CustomCalloutExtensionConfig]);

/** The markdown export of a document holding one callout over one paragraph. */
function exportMarkdown(attrs: Record<string, unknown>): string {
  const doc = schema.node("doc", null, [
    schema.node("calloutComponent", attrs, [schema.node("paragraph", null, [schema.text("Body text")])]),
    schema.node("paragraph", null, [schema.text("After")]),
  ]);
  const serializer = new MarkdownSerializer(
    {
      ...defaultMarkdownSerializer.nodes,
      calloutComponent: storage.markdown.serialize,
    },
    defaultMarkdownSerializer.marks
  );
  return serializer.serialize(doc);
}

const encode = (text: string): string => [...text].map((c) => c.codePointAt(0)).join("-");
const INJECTION = "\n\n![](https://evil.example/t.png)\n<img src=x onerror=alert(1)>";

describe("a callout exported as markdown", () => {
  it("writes the emoji itself, never an image on another host", () => {
    const markdown = exportMarkdown({
      "data-logo-in-use": "emoji",
      "data-emoji-unicode": "128161",
      // Stored by older versions, and by the picker: it must not be exported.
      "data-emoji-url": "https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/1f4a1.png",
    });
    expect(markdown).toBe("> 💡\n> \n> Body text\n\nAfter");
  });

  it("writes the icon name when an icon is in use", () => {
    expect(exportMarkdown({ "data-logo-in-use": "icon", "data-icon-name": "Info" })).toBe(
      "> <icon>Info icon</icon>\n> \n> Body text\n\nAfter"
    );
  });

  it("leaves out an emoji whose code points spell markup", () => {
    const markdown = exportMarkdown({ "data-logo-in-use": "emoji", "data-emoji-unicode": encode(INJECTION) });
    expect(markdown).toBe("> \n> Body text\n\nAfter");
  });

  it("leaves out an icon name that is not a plain identifier", () => {
    const markdown = exportMarkdown({ "data-logo-in-use": "icon", "data-icon-name": `Info${INJECTION}` });
    expect(markdown).toBe("> \n> Body text\n\nAfter");
  });

  it.each([
    ["emoji", { "data-logo-in-use": "emoji", "data-emoji-unicode": encode(INJECTION) }],
    ["icon", { "data-logo-in-use": "icon", "data-icon-name": `x</icon>${INJECTION}` }],
  ])("never lets a crafted %s reach the export", (_kind, attrs) => {
    const markdown = exportMarkdown(attrs);
    expect(markdown).not.toMatch(/evil\.example|<img|onerror|!\[/);
  });
});
