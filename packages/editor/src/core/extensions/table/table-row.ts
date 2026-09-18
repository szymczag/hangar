/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { mergeAttributes, Node } from "@tiptap/core";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// helpers
import { sanitizeColorKey } from "@/helpers/attribute-guards";

type TableRowOptions = {
  HTMLAttributes: Record<string, unknown>;
};

export const TableRow = Node.create<TableRowOptions>({
  name: CORE_EXTENSIONS.TABLE_ROW,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  addAttributes() {
    return {
      // Palette keys only. Read from the data attributes this node renders,
      // or from the legacy `background`/`textcolor` attributes older content
      // stored as CSS variables. Rendered as data attributes coloured by
      // editor.css, never as inline style (CSS injection, and refused by a
      // strict Content-Security-Policy).
      background: {
        default: null,
        parseHTML: (element) =>
          sanitizeColorKey(element.getAttribute("data-background-color") ?? element.getAttribute("background")),
        renderHTML: (attributes) => {
          const background = sanitizeColorKey(attributes.background);
          return background ? { "data-background-color": background } : {};
        },
      },
      textColor: {
        default: null,
        parseHTML: (element) =>
          sanitizeColorKey(element.getAttribute("data-text-color") ?? element.getAttribute("textcolor")),
        renderHTML: (attributes) => {
          const textColor = sanitizeColorKey(attributes.textColor);
          return textColor ? { "data-text-color": textColor } : {};
        },
      },
    };
  },

  content: "(tableCell | tableHeader)*",

  tableRole: "row",

  parseHTML() {
    return [{ tag: "tr" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["tr", mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0];
  },
});
