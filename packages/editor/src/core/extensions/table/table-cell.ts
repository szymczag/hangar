/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { mergeAttributes, Node } from "@tiptap/core";
import { TableMap } from "@tiptap/pm/tables";
// constants
import { CORE_EXTENSIONS } from "@/constants/extension";
// helpers
import { sanitizeColorKey } from "@/helpers/attribute-guards";
import { findParentNodeOfType } from "@/helpers/common";
// local imports
import { TableCellSelectionOutlinePlugin } from "./plugins/selection-outline/plugin";
import { DEFAULT_COLUMN_WIDTH } from "./table";
import { isCellSelection } from "./table/utilities/helpers";

type TableCellOptions = {
  HTMLAttributes: Record<string, unknown>;
};

export const TableCell = Node.create<TableCellOptions>({
  name: CORE_EXTENSIONS.TABLE_CELL,

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

  tableRole: "cell",

  isolating: true,

  addProseMirrorPlugins() {
    return [TableCellSelectionOutlinePlugin(this.editor)];
  },

  addKeyboardShortcuts() {
    return {
      Backspace: ({ editor }) => {
        const { state } = editor.view;
        const { selection } = state;

        if (isCellSelection(selection)) return false;

        // Check if we're at the start of the cell
        if (selection.from !== selection.to || selection.$head.parentOffset !== 0) return false;

        // Find table and current cell
        const tableNode = findParentNodeOfType(selection, [CORE_EXTENSIONS.TABLE])?.node;
        const currentCellInfo = findParentNodeOfType(selection, [
          CORE_EXTENSIONS.TABLE_CELL,
          CORE_EXTENSIONS.TABLE_HEADER,
        ]);
        const currentCellNode = currentCellInfo?.node;
        const cellPos = currentCellInfo?.pos;
        const cellDepth = currentCellInfo?.depth;

        if (!tableNode || !currentCellNode || cellPos === null || cellDepth === null) return false;

        // Check if this is the only cell in the TableMap (1 row, 1 column)
        const tableMap = TableMap.get(tableNode);
        const isOnlyCell = tableMap.width === 1 && tableMap.height === 1;
        if (!isOnlyCell) return false;

        // Cell has content, select the entire cell
        // Use the position that points to the cell node itself, not its content
        const cellNodePos = selection.$head.before(cellDepth);

        editor.commands.setCellSelection({
          anchorCell: cellNodePos,
          headCell: cellNodePos,
        });
        return true;
      },
    };
  },

  parseHTML() {
    return [{ tag: "td" }];
  },

  renderHTML({ HTMLAttributes }) {
    return ["td", mergeAttributes(this.options.HTMLAttributes, HTMLAttributes), 0];
  },
});
