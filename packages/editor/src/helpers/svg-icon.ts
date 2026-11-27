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

/**
 * Propel's `MoreVerticalOutline`, drawn twice side by side as the drag handle.
 * The glyph upstream mounts as a React root (`plugins/handle-icon.ts`); here it
 * is the same path data, built as plain DOM. The `<g fill>` wrapper of the
 * generated component is folded into the path.
 */
export const VERTICAL_ELLIPSIS_ICON: TSvgIcon = {
  attributes: {
    width: "14",
    height: "14",
    viewBox: "0 0 16 16",
    fill: "none",
    "aria-hidden": "true",
    class: "shrink-0",
  },
  children: [
    {
      tag: "path",
      attributes: {
        fill: "currentColor",
        d: "M7.708 8.083a.04.04 0 0 0-.041-.042.04.04 0 0 0-.042.042c0 .023.02.041.042.041s.04-.018.041-.041m1.25 0a1.291 1.291 0 1 1-2.582 0 1.291 1.291 0 0 1 2.582 0M7.708 3.417a.04.04 0 0 0-.041-.042.04.04 0 0 0-.042.042c0 .023.02.041.042.041s.04-.018.041-.041m1.25 0a1.291 1.291 0 1 1-2.582 0 1.291 1.291 0 0 1 2.582 0M7.708 12.75a.04.04 0 0 0-.041-.042.04.04 0 0 0-.042.042c0 .023.02.041.042.041s.04-.018.041-.041m1.25 0a1.291 1.291 0 1 1-2.582 0 1.291 1.291 0 0 1 2.582 0",
      },
    },
  ],
};

/** Propel's `AiStarFourOutline`, the AI handle */
export const SPARKLES_ICON: TSvgIcon = {
  attributes: {
    width: "14",
    height: "14",
    viewBox: "0 0 16 16",
    fill: "none",
    "aria-hidden": "true",
    class: "shrink-0",
  },
  children: [
    {
      tag: "path",
      attributes: {
        fill: "currentColor",
        d: "M2.375 14.666v-1.041H1.334a.625.625 0 0 1 0-1.25h1.041v-1.042a.625.625 0 1 1 1.25 0v1.042h1.042a.625.625 0 1 1 0 1.25H3.625v1.041a.625.625 0 0 1-1.25 0M8.666 1.375c.26 0 .492.159.584.4l1.157 3.006c.2.518.264.675.353.801q.136.189.325.324c.126.09.282.154.8.354l3.006 1.156a.626.626 0 0 1 0 1.167l-3.006 1.156c-.518.2-.674.265-.8.355a1.4 1.4 0 0 0-.325.323c-.09.126-.154.283-.353.8L9.25 14.225a.627.627 0 0 1-1.166 0l-1.157-3.006c-.2-.519-.264-.675-.354-.801a1.4 1.4 0 0 0-.323-.323c-.127-.09-.283-.155-.801-.355L2.443 8.583a.626.626 0 0 1 0-1.167L5.449 6.26c.518-.2.674-.264.8-.354q.19-.135.324-.324c.09-.126.155-.282.354-.8l1.157-3.007.04-.087a.63.63 0 0 1 .542-.313m-.572 3.854c-.176.46-.3.793-.502 1.078-.17.239-.379.448-.618.618-.285.202-.618.325-1.077.502l-1.49.572 1.49.573c.459.177.792.3 1.077.502.24.17.448.38.618.618.203.285.326.619.502 1.078l.572 1.488.574-1.488c.176-.46.3-.793.502-1.078.17-.239.379-.448.618-.618.285-.202.618-.325 1.077-.502L12.925 8l-1.488-.572c-.459-.177-.792-.3-1.077-.502a2.6 2.6 0 0 1-.618-.618c-.203-.285-.326-.619-.502-1.078L8.666 3.74zm-5.719-.563V3.625H1.334a.625.625 0 0 1 0-1.25h1.041V1.333a.625.625 0 1 1 1.25 0v1.042h1.042a.625.625 0 1 1 0 1.25H3.625v1.041a.625.625 0 0 1-1.25 0",
      },
    },
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
