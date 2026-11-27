/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Extensions, JSONContent } from "@tiptap/core";
import { getSchema } from "@tiptap/core";
import { generateHTML, generateJSON } from "@tiptap/html/server";
import type { MarkType, NodeType, Schema } from "@tiptap/pm/model";
import { describe, expect, it } from "vitest";
import {
  CoreEditorExtensionsWithoutProps,
  DocumentEditorExtensionsWithoutProps,
} from "../src/extensions/core-without-props";
import { CoreEditorExtensions } from "../src/extensions/extensions";
import type { TFileHandler, TMentionHandler } from "../src/types";

/**
 * Live reads and writes the same Yjs documents the browser editor edits, and
 * converts them to HTML and JSON, with the schema of the server extension set
 * (`CoreEditorExtensionsWithoutProps`). That set is built from schema-only
 * configs (no node views, menus or plugins, tests/lib-entry-ui-free.test.ts);
 * the browser's extensions extend those configs. A node, mark, attribute or
 * default that exists on one side only is content the other side drops or
 * invents, so the two schemas must stay equal.
 *
 * Three differences predate the split and are named here, so any other one
 * fails:
 * - the browser's `UniqueID` extension adds an `id` attribute (default null) to
 *   block nodes; live does not assign block ids, and a stored id is dropped
 *   when live builds HTML or JSON from the document, as before;
 * - `tiptap-markdown` (browser only, for markdown paste and copy) adds `tight`
 *   to the list nodes;
 * - the browser's callout and image components are `selectable` and
 *   `draggable`, which affects selection, not content.
 */

const stub = () => undefined;
const fileHandler = {
  assetsUploadStatus: {},
  cancel: stub,
  checkIfAssetExists: async () => true,
  delete: async () => undefined,
  getAssetDownloadSrc: async (path: string) => path,
  getAssetSrc: async (path: string) => path,
  restore: async () => undefined,
  upload: async () => "",
  duplicate: async () => "",
  validation: { maxFileSize: 5 * 1024 * 1024 },
} as unknown as TFileHandler;
const mentionHandler = {
  renderComponent: () => null,
  getMentionedEntityDetails: () => undefined,
  searchCallback: async () => [],
} as unknown as TMentionHandler;

const browserExtensions = (): Extensions =>
  CoreEditorExtensions({
    disabledExtensions: [],
    flaggedExtensions: [],
    editable: true,
    enableHistory: true,
    extendedEditorProps: {},
    fileHandler,
    getEditorMetaData: () => ({ file_assets: [], user_mentions: [] }) as never,
    isTouchDevice: false,
    mentionHandler,
    placeholder: "",
    showPlaceholderOnEmpty: false,
    tabIndex: 0,
    provider: undefined,
  });
const serverExtensions = (): Extensions => CoreEditorExtensionsWithoutProps;

type TTypeDescription = {
  attrs: Record<string, unknown>;
  spec: Record<string, unknown>;
  parse: unknown[];
};

const describeType = (type: NodeType | MarkType): TTypeDescription => {
  const spec = type.spec as Record<string, unknown>;
  const attrSpecs = (spec.attrs ?? {}) as Record<string, { default?: unknown }>;
  return {
    attrs: Object.fromEntries(
      Object.keys(attrSpecs)
        .toSorted()
        .map((name) => [name, attrSpecs[name].default])
    ),
    spec: Object.fromEntries(
      Object.entries(spec)
        .filter(([key, value]) => typeof value !== "function" && key !== "attrs" && key !== "parseDOM")
        .toSorted(([a], [b]) => a.localeCompare(b))
    ),
    parse: ((spec.parseDOM ?? []) as Record<string, unknown>[]).map(({ tag, style, priority, consuming, context }) => ({
      tag,
      style,
      priority,
      consuming,
      context,
    })),
  };
};

const describeSchema = (schema: Schema): Record<string, TTypeDescription> => ({
  ...Object.fromEntries(Object.entries(schema.nodes).map(([name, type]) => [`node:${name}`, describeType(type)])),
  ...Object.fromEntries(Object.entries(schema.marks).map(([name, type]) => [`mark:${name}`, describeType(type)])),
});

/** What the browser schema has and the server's does not, as `type.attrs.name` / `type.spec.key` paths. */
const browserOnly = (server: Record<string, TTypeDescription>, browser: Record<string, TTypeDescription>) => {
  const paths: string[] = [];
  for (const [type, description] of Object.entries(browser)) {
    for (const part of ["attrs", "spec"] as const) {
      for (const key of Object.keys(description[part])) {
        if (!(key in (server[type]?.[part] ?? {}))) paths.push(`${type}.${part}.${key}`);
      }
    }
  }
  return paths.toSorted();
};

const KNOWN_BROWSER_ONLY = [
  ...[
    "blockquote",
    "bulletList",
    "codeBlock",
    "heading",
    "horizontalRule",
    "image",
    "listItem",
    "orderedList",
    "paragraph",
    "table",
    "taskItem",
    "taskList",
  ].map((node) => `node:${node}.attrs.id`),
  "node:bulletList.attrs.tight",
  "node:orderedList.attrs.tight",
  "node:calloutComponent.spec.draggable",
  "node:calloutComponent.spec.selectable",
  "node:imageComponent.spec.selectable",
].toSorted();

/** Remove the named browser-only differences, so the rest must be equal. */
const withoutKnownBrowserOnly = (described: Record<string, TTypeDescription>) => {
  const copy = structuredClone(described);
  for (const path of KNOWN_BROWSER_ONLY) {
    const [type, part, key] = path.split(".") as [string, "attrs" | "spec", string];
    delete copy[type]?.[part][key];
  }
  return copy;
};

const stripBrowserOnlyAttrs = (node: JSONContent): JSONContent => {
  const copy: JSONContent = { ...node };
  if (copy.attrs) {
    const attrs = { ...copy.attrs };
    for (const path of KNOWN_BROWSER_ONLY) {
      const [type, part, key] = path.split(".");
      if (part === "attrs" && type === `node:${node.type}`) delete attrs[key];
    }
    if (Object.keys(attrs).length > 0) copy.attrs = attrs;
    else delete copy.attrs;
  }
  if (copy.content) copy.content = copy.content.map(stripBrowserOnlyAttrs);
  if (copy.marks) copy.marks = copy.marks.map((mark) => stripBrowserOnlyAttrs(mark) as typeof mark);
  return copy;
};

const paragraph = (...content: JSONContent[]): JSONContent => ({ type: "paragraph", content });
type TMark = NonNullable<JSONContent["marks"]>[number];
const text = (value: string, marks?: TMark[]): JSONContent => ({
  type: "text",
  text: value,
  ...(marks ? { marks } : {}),
});
const cell = (type: "tableHeader" | "tableCell", value: string, attrs: Record<string, unknown> = {}): JSONContent => ({
  type,
  attrs: { colspan: 1, rowspan: 1, colwidth: [150], ...attrs },
  content: [paragraph(text(value))],
});

/** One page with every node the editor menus act on. */
const FIXTURE: JSONContent = {
  type: "doc",
  content: [
    { type: "heading", attrs: { level: 2 }, content: [text("Fixture")] },
    paragraph(
      text("A "),
      text("link", [{ type: "link", attrs: { href: "https://example.com/docs" } }]),
      text(", a mention "),
      {
        type: "mention",
        attrs: { id: "6f8c7f8e-1b5a-4c9e-9a59-0d8d1c2b3a4f", entity_identifier: "user-1", entity_name: "user_mention" },
      },
      text(" and an emoji "),
      { type: "emoji", attrs: { name: "rocket" } },
      text(" with "),
      text("colour", [{ type: "customColor", attrs: { color: "peach", backgroundColor: "light-blue" } }])
    ),
    {
      type: "table",
      content: [
        {
          type: "tableRow",
          attrs: { background: "gray" },
          content: [cell("tableHeader", "Name", { background: "purple" }), cell("tableHeader", "Value")],
        },
        {
          type: "tableRow",
          content: [cell("tableCell", "a", { background: "green", textColor: "dark-blue" }), cell("tableCell", "1")],
        },
      ],
    },
    {
      type: "imageComponent",
      attrs: { id: "b6a1d1d2-8f61-4a54-9c3b-6c2f5a0f9e11", src: "asset-1", width: "320px", alignment: "center" },
    },
    {
      type: "codeBlock",
      attrs: { language: "typescript" },
      content: [text('const greeting = "hello";\nconsole.log(greeting);')],
    },
    {
      type: "calloutComponent",
      attrs: { "data-emoji-unicode": "128640", "data-background": "orange" },
      content: [paragraph(text("A callout"))],
    },
    {
      type: "taskList",
      content: [{ type: "taskItem", attrs: { checked: true }, content: [paragraph(text("done"))] }],
    },
  ],
};

// Unchanged from upstream: the server's task item has `class="flex"`, the
// browser's `class="relative"`; the browser's code block writes an empty
// `class` on <pre>; and its `UniqueID` writes `data-id` next to the image
// component's own `id`.
const normaliseHTML = (html: string) =>
  html
    .replace(/<li class="(?:flex|relative)" (data-checked="true" data-type="taskItem")/, "<li $1")
    .replace('<pre class="">', "<pre>")
    .replace(/ data-id="[^"]*"/g, "");

const roundTrip = (extensions: Extensions) => {
  const html = generateHTML(FIXTURE, extensions);
  const json = generateJSON(html, extensions);
  return { html, json, again: generateJSON(generateHTML(json, extensions), extensions) };
};

describe("the server and browser editor schemas", () => {
  const server = describeSchema(getSchema(serverExtensions()));
  const browser = describeSchema(getSchema(browserExtensions()));

  it("have the same nodes and marks", () => {
    expect(Object.keys(server).toSorted()).toEqual(Object.keys(browser).toSorted());
  });

  it("differ only by the named browser-only attributes and flags", () => {
    expect(browserOnly(server, browser)).toEqual(KNOWN_BROWSER_ONLY);
    expect(browserOnly(browser, server)).toEqual([]);
  });

  it("have the same attributes, defaults, content rules and parse rules otherwise", () => {
    expect(withoutKnownBrowserOnly(browser)).toEqual(server);
  });

  it("the document set adds only the work item embed node", () => {
    const document = describeSchema(
      getSchema([...CoreEditorExtensionsWithoutProps, ...DocumentEditorExtensionsWithoutProps])
    );
    expect(Object.keys(document).filter((type) => !(type in server))).toEqual(["node:issue-embed-component"]);
  });
});

describe("a page with a table, image, code block, callout, link, mention and emoji", () => {
  const server = roundTrip(serverExtensions());
  const browser = roundTrip(browserExtensions());

  it("parses to the same JSON on both sides", () => {
    expect(stripBrowserOnlyAttrs(browser.json)).toEqual(server.json);
  });

  it("round-trips through HTML and JSON without change on both sides", () => {
    expect(server.again).toEqual(server.json);
    expect(browser.again).toEqual(browser.json);
  });

  it("keeps every fixture node on both sides", () => {
    for (const { json } of [server, browser]) {
      const types = new Set<string>();
      const walk = (node: JSONContent) => {
        if (node.type) types.add(node.type);
        node.marks?.forEach(walk);
        node.content?.forEach(walk);
      };
      walk(json);
      for (const type of [
        "table",
        "tableHeader",
        "tableCell",
        "imageComponent",
        "codeBlock",
        "calloutComponent",
        "link",
        "mention",
        "customColor",
        "taskItem",
      ]) {
        expect(types).toContain(type);
      }
    }
  });

  it("turns an emoji node into its character on both sides", () => {
    // Known and unchanged by the split: ProseMirror tries mark parse rules
    // before node rules, and `customColor` matches every <span>, so the emoji's
    // <span data-type="emoji"> becomes its character under an empty colour
    // mark. Upstream v1.5.0 parses it the same way. The Yjs path never parses
    // HTML, so collaborative edits keep the node.
    for (const { json } of [server, browser]) {
      const serialised = JSON.stringify(json);
      expect(serialised).not.toContain('"type":"emoji"');
      expect(serialised).toContain("🚀");
    }
  });

  it("renders the same HTML on both sides, but for presentation-only attributes", () => {
    expect(normaliseHTML(browser.html)).toEqual(normaliseHTML(server.html));
    expect(server.html).not.toContain("data-id=");
  });
});
