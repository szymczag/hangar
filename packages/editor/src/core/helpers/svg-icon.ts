/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Icons the editor's plain-DOM widgets (drag handle, AI handle, table insert
// buttons) draw, built with createElementNS instead of assigned as an HTML
// string. innerHTML is a sink Trusted Types guards; an icon has no reason to
// go through an HTML parser at all (docs/trusted-types-plan.md, phase 1).

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

export type TSvgIcon = {
  readonly attributes: Readonly<Record<string, string>>;
  readonly children: ReadonlyArray<{
    readonly tag: "path" | "circle";
    readonly attributes: Readonly<Record<string, string>>;
  }>;
};

/** A fresh `<svg>` element for the icon, owned by `doc`. */
export const createSvgIcon = (icon: TSvgIcon, doc: Document = document): SVGSVGElement => {
  const svg = doc.createElementNS(SVG_NAMESPACE, "svg");
  for (const [name, value] of Object.entries(icon.attributes)) svg.setAttribute(name, value);
  for (const child of icon.children) {
    const element = doc.createElementNS(SVG_NAMESPACE, child.tag);
    for (const [name, value] of Object.entries(child.attributes)) element.setAttribute(name, value);
    svg.appendChild(element);
  }
  return svg;
};

/** lucide ellipsis-vertical, drawn twice side by side as the drag handle */
export const VERTICAL_ELLIPSIS_ICON: TSvgIcon = {
  attributes: {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    class: "lucide lucide-ellipsis-vertical",
  },
  children: [
    { tag: "circle", attributes: { cx: "12", cy: "12", r: "1" } },
    { tag: "circle", attributes: { cx: "12", cy: "5", r: "1" } },
    { tag: "circle", attributes: { cx: "12", cy: "19", r: "1" } },
  ],
};

/** lucide sparkles, the AI handle */
export const SPARKLES_ICON: TSvgIcon = {
  attributes: {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    class: "lucide lucide-sparkles",
  },
  children: [
    {
      tag: "path",
      attributes: {
        d: "M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z",
      },
    },
    { tag: "path", attributes: { d: "M20 3v4" } },
    { tag: "path", attributes: { d: "M22 5h-4" } },
    { tag: "path", attributes: { d: "M4 17v2" } },
    { tag: "path", attributes: { d: "M5 18H3" } },
  ],
};

/** plus, the table's insert-column and insert-row buttons */
export const ADD_ICON: TSvgIcon = {
  attributes: { width: "16", height: "16", viewBox: "0 0 16 16", fill: "none" },
  children: [
    {
      tag: "path",
      attributes: {
        d: "M8.5 7.49988V3.49988C8.5 3.22374 8.27614 2.99988 8 2.99988C7.72386 2.99988 7.5 3.22374 7.5 3.49988L7.5 7.49988L3.5 7.49988C3.22386 7.49988 3 7.72374 3 7.99988C3 8.27602 3.22386 8.49988 3.5 8.49988H7.5L7.5 12.4999C7.5 12.776 7.72386 12.9999 8 12.9999C8.27614 12.9999 8.5 12.776 8.5 12.4999L8.5 8.49988L12.5 8.49988C12.7761 8.49988 13 8.27602 13 7.99988C13 7.72374 12.7761 7.49988 12.5 7.49988L8.5 7.49988Z",
        fill: "currentColor",
      },
    },
  ],
};
