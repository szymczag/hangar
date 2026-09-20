/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { describe, expect, it } from "vitest";

import { ADD_ICON, SPARKLES_ICON, VERTICAL_ELLIPSIS_ICON, createSvgIcon } from "../src/core/helpers/svg-icon";
import previous from "./fixtures-previous-icon-markup.json";

type TNode = { namespace: string; tag: string; attributes: Record<string, string>; children: TNode[] };

/** Just enough of a Document to record what createSvgIcon builds. */
const recordingDocument = () =>
  ({
    createElementNS: (namespace: string, tag: string) => {
      const node: TNode & { setAttribute: unknown; appendChild: unknown } = {
        namespace,
        tag,
        attributes: {},
        children: [],
        setAttribute(name: string, value: string) {
          node.attributes[name] = value;
        },
        appendChild(child: TNode) {
          node.children.push(child);
          return child;
        },
      };
      return node;
    },
  }) as unknown as Document;

const plain = (node: TNode): TNode => ({
  namespace: node.namespace,
  tag: node.tag,
  attributes: { ...node.attributes },
  children: node.children.map(plain),
});

const attributes = (source: string) =>
  Object.fromEntries([...source.matchAll(/([a-zA-Z:-]+)="([^"]*)"/g)].map((match) => [match[1], match[2]]));

/** The markup the widgets used to assign to innerHTML, as a tree. */
const parsePrevious = (markup: string): TNode => {
  const svg = /<svg([^>]*)>/.exec(markup)!;
  const { xmlns, ...svgAttributes } = attributes(svg[1]);
  expect(xmlns).toBe("http://www.w3.org/2000/svg");
  return {
    namespace: xmlns,
    tag: "svg",
    attributes: svgAttributes,
    children: [...markup.matchAll(/<(path|circle)\b([^>]*?)\/>/g)].map((match) => ({
      namespace: xmlns,
      tag: match[1],
      attributes: attributes(match[2]),
      children: [],
    })),
  };
};

describe("createSvgIcon", () => {
  it.each([
    ["VERTICAL_ELLIPSIS_ICON", VERTICAL_ELLIPSIS_ICON],
    ["SPARKLES_ICON", SPARKLES_ICON],
    ["ADD_ICON", ADD_ICON],
  ] as const)("builds %s exactly as the markup it replaces", (name, icon) => {
    const built = plain(createSvgIcon(icon, recordingDocument()) as unknown as TNode);
    expect(built).toEqual(parsePrevious(previous[name]));
  });
});
