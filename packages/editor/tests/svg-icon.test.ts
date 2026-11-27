/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AiStarFourOutline, MoreVerticalOutline } from "@makeplane/propel/icons";
import type { ComponentType, SVGProps } from "react";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ADD_ICON, SPARKLES_ICON, VERTICAL_ELLIPSIS_ICON, createSvgIcon } from "../src/helpers/svg-icon";
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

/**
 * The path data a Propel icon component renders, with any `fill` inherited
 * from a wrapping `<g>` folded into each path, as the plain-DOM icon carries it.
 */
const propelGlyph = (icon: ComponentType<SVGProps<SVGSVGElement>>) => {
  const markup = renderToStaticMarkup(createElement(icon, { width: 14, height: 14 }));
  const svg = attributes(/<svg([^>]*)>/.exec(markup)![1]);
  const groupFill = /<g([^>]*)>/.exec(markup)?.[1];
  const inherited = groupFill ? attributes(groupFill) : {};
  return {
    viewBox: svg.viewBox,
    paths: [...markup.matchAll(/<path\b([^>]*?)\/?>/g)].map((match) =>
      Object.assign({}, inherited, attributes(match[1]))
    ),
  };
};

describe("createSvgIcon", () => {
  it("builds ADD_ICON exactly as the markup it replaces", () => {
    const built = plain(createSvgIcon(ADD_ICON, recordingDocument()) as unknown as TNode);
    expect(built).toEqual(parsePrevious(previous.ADD_ICON));
  });

  // The side-menu handles draw Propel's glyphs, as upstream does, but as plain
  // DOM: upstream mounts each icon as its own React root (plugins/handle-icon.ts).
  it.each([
    ["VERTICAL_ELLIPSIS_ICON", VERTICAL_ELLIPSIS_ICON, MoreVerticalOutline],
    ["SPARKLES_ICON", SPARKLES_ICON, AiStarFourOutline],
  ] as const)("builds %s with the path data of its Propel icon", (_name, icon, component) => {
    const built = plain(createSvgIcon(icon, recordingDocument()) as unknown as TNode);
    const glyph = propelGlyph(component);
    expect(built.namespace).toBe("http://www.w3.org/2000/svg");
    expect(built.attributes).toMatchObject({ width: "14", height: "14", viewBox: glyph.viewBox });
    expect(built.children.map((child) => ({ tag: child.tag, attributes: child.attributes }))).toEqual(
      glyph.paths.map((path) => ({ tag: "path", attributes: path }))
    );
  });
});
