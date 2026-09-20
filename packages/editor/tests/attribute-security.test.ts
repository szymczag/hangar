/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { getSchema } from "@tiptap/core";
import type { Mark, Node as ProseMirrorNode } from "@tiptap/pm/model";
import { generateJSON } from "@tiptap/html";
import { describe, expect, it } from "vitest";

import { COLORS_LIST } from "../src/core/constants/common";
import { CoreEditorExtensionsWithoutProps } from "../src/core/extensions/core-without-props";
import { normalizeDocumentJSON, sanitizeColorKey, sanitizeTextAlign } from "../src/core/helpers/attribute-guards";

const OVERLAY = "position:fixed;inset:0;z-index:99999;background:url(https://attacker.example/px)";

const schema = getSchema(CoreEditorExtensionsWithoutProps);

type TRenderedAttributes = Record<string, unknown>;

/** The attributes ProseMirror would set on the DOM element, for every node and mark. */
const renderedAttributes = (doc: ProseMirrorNode): TRenderedAttributes[] => {
  const rendered: TRenderedAttributes[] = [];
  const collect = (spec: unknown) => {
    if (Array.isArray(spec) && spec[1] && typeof spec[1] === "object" && !Array.isArray(spec[1])) {
      rendered.push(spec[1] as TRenderedAttributes);
    }
  };
  doc.descendants((node) => {
    collect(node.type.spec.toDOM?.(node));
    node.marks.forEach((mark: Mark) => collect(mark.type.spec.toDOM?.(mark, true)));
  });
  return rendered;
};

const fromHTML = (html: string) => schema.nodeFromJSON(generateJSON(html, CoreEditorExtensionsWithoutProps));

const expectNoInjectedStyle = (doc: ProseMirrorNode) => {
  for (const attributes of renderedAttributes(doc)) {
    expect(attributes).not.toHaveProperty("style");
    expect(JSON.stringify(attributes)).not.toContain("position");
    expect(JSON.stringify(attributes)).not.toContain("attacker.example");
  }
};

describe("attribute guards", () => {
  it("accepts palette keys and their legacy CSS variables only", () => {
    expect(sanitizeColorKey("gray")).toBe("gray");
    expect(sanitizeColorKey("var(--editor-colors-light-blue-background)")).toBe("light-blue");
    expect(sanitizeColorKey(`red;${OVERLAY}`)).toBeNull();
    expect(sanitizeColorKey("#ff0000")).toBeNull();
    expect(sanitizeColorKey(undefined)).toBeNull();
  });

  it("accepts the supported alignments only", () => {
    expect(sanitizeTextAlign("center")).toBe("center");
    expect(sanitizeTextAlign("justify")).toBeNull();
    expect(sanitizeTextAlign("center;color:red")).toBeNull();
  });
});

describe("rendered attributes from stored HTML", () => {
  it.each([
    [`<p><span data-text-color="red;${OVERLAY}">x</span></p>`],
    [`<p><span data-background-color="red;${OVERLAY}">x</span></p>`],
    [`<table><tbody><tr><td background="red;${OVERLAY}"><p>x</p></td></tr></tbody></table>`],
    [`<table><tbody><tr><th background="red;${OVERLAY}"><p>x</p></th></tr></tbody></table>`],
    [`<table><tbody><tr background="red" textcolor="red;${OVERLAY}"><td><p>x</p></td></tr></tbody></table>`],
    [`<p style="${OVERLAY}">x</p>`],
  ])("never carries an inline style: %s", (html) => {
    expectNoInjectedStyle(fromHTML(html));
  });

  it("renders palette colours and alignment as data attributes", () => {
    const attributes = renderedAttributes(
      fromHTML(
        '<p data-text-align="center"><span data-text-color="gray">x</span></p>' +
          '<table><tbody><tr><td background="var(--editor-colors-peach-background)"><p>y</p></td></tr></tbody></table>'
      )
    );
    expect(attributes).toContainEqual(expect.objectContaining({ "data-text-align": "center" }));
    expect(attributes).toContainEqual(expect.objectContaining({ "data-text-color": "gray" }));
    expect(attributes).toContainEqual(expect.objectContaining({ "data-background-color": "peach" }));
  });

  it("still reads the alignment older content stored as inline style", () => {
    // generateJSON parses with a DOM that exposes element.style.
    const attributes = renderedAttributes(fromHTML('<p style="text-align: right">x</p>'));
    expect(attributes).toContainEqual(expect.objectContaining({ "data-text-align": "right" }));
  });

  it("fixes link target, rel and class instead of taking them from content", () => {
    const attributes = renderedAttributes(
      fromHTML('<p><a href="https://example.com" target="_self" rel="opener" class="fixed inset-0 z-50">x</a></p>')
    );
    const link = attributes.find((attrs) => "href" in attrs);
    expect(link).toMatchObject({ href: "https://example.com", target: "_blank", rel: "noopener noreferrer nofollow" });
    expect(String(link?.class)).not.toContain("fixed");
  });
});

describe("rendered attributes from the collaborative document", () => {
  // A collaborative update is applied as document JSON and never passes
  // parseHTML, so the guards in renderHTML are what stand between it and the DOM.
  it("guards node and mark attributes on render", () => {
    const doc = schema.nodeFromJSON({
      type: "doc",
      content: [
        {
          type: "paragraph",
          attrs: { textAlign: `center;${OVERLAY}` },
          content: [
            {
              type: "text",
              text: "x",
              marks: [
                { type: "customColor", attrs: { color: `red;${OVERLAY}`, backgroundColor: `red;${OVERLAY}` } },
                { type: "link", attrs: { href: "https://example.com", target: "_self", class: "fixed inset-0" } },
              ],
            },
          ],
        },
        {
          type: "table",
          content: [
            {
              type: "tableRow",
              attrs: { background: `red;${OVERLAY}`, textColor: `red;${OVERLAY}` },
              content: [
                {
                  type: "tableCell",
                  attrs: { background: `red;${OVERLAY}`, textColor: `red;${OVERLAY}` },
                  content: [{ type: "paragraph" }],
                },
                {
                  type: "tableHeader",
                  attrs: { background: `red;${OVERLAY}` },
                  content: [{ type: "paragraph" }],
                },
              ],
            },
          ],
        },
      ],
    });

    expectNoInjectedStyle(doc);
    const link = renderedAttributes(doc).find((attrs) => "href" in attrs);
    expect(link).toMatchObject({ target: "_blank" });
    expect(String(link?.class)).not.toContain("fixed");
  });
});

describe("palette contract with the API sanitizer", () => {
  it("lists the same colour keys as content_validator.py", () => {
    const validator = readFileSync(resolve(__dirname, "../../../apps/api/plane/utils/content_validator.py"), "utf-8");
    const match = /EDITOR_COLOR_KEYS = frozenset\(\{([^}]*)\}\)/.exec(validator);
    expect(match).not.toBeNull();
    const pythonKeys = [...(match?.[1] ?? "").matchAll(/"([a-z-]+)"/g)].map((key) => key[1]).toSorted();
    expect(pythonKeys).toEqual(COLORS_LIST.map((color) => color.key).toSorted());
  });
});

describe("stored document JSON", () => {
  it("carries only the values the editor would render", () => {
    const normalized = normalizeDocumentJSON({
      type: "doc",
      content: [
        {
          type: "paragraph",
          attrs: { textAlign: "center;color:red" },
          content: [
            {
              type: "text",
              text: "x",
              marks: [
                { type: "customColor", attrs: { color: `red;${OVERLAY}`, backgroundColor: "gray" } },
                { type: "link", attrs: { href: "https://example.com", target: "_self", class: "fixed" } },
              ],
            },
          ],
        },
        {
          type: "table",
          content: [
            {
              type: "tableRow",
              attrs: { background: "var(--editor-colors-green-background)" },
              content: [{ type: "tableCell", attrs: { background: `red;${OVERLAY}` }, content: [] }],
            },
          ],
        },
      ],
    });

    const serialized = JSON.stringify(normalized);
    expect(serialized).not.toContain("position");
    expect(serialized).not.toContain("_self");
    expect(serialized).not.toContain("fixed");
    expect(serialized).toContain('"backgroundColor":"gray"');
    expect(serialized).toContain('"background":"green"');
    expect(serialized).toContain('"href":"https://example.com"');
  });
});
