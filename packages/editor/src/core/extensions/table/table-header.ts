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
// local imports
import { DEFAULT_COLUMN_WIDTH } from "./table";

type TableHeaderOptions = {
  HTMLAttributes: Record<string, unknown>;
};

export const TableHeader = Node.create<TableHeaderOptions>({
  name: CORE_EXTENSIONS.TABLE_HEADER,

  addOptions() {
    return {
      HTMLAttributes: {},
    };
  },

  content: "block+",

  addAttributes() {
    return {
      colspan: {
        default: 1,
      },
      rowspan: {
        default: 1,
      },
      colwidth: {
        default: [DEFAULT_COLUMN_WIDTH],
        parseHTML: (element) => {
          const colwidth = element.getAttribute("colwidth");
          const value = colwidth ? [parseInt(colwidth, 10)] : null;

          return value;
        },
      },
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
    };
  },

  tableRole: "header_cell",

  isolating: true,

  parseHTML() {
    return [{ tag: "th" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["th", mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0];
  },
});
