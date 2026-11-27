/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { columnResizing, tableEditing } from "@tiptap/pm/tables";
// local imports
import { TableDragStatePlugin } from "../plugins/drag-state";
import { TableColumnDragHandlePlugin } from "../plugins/drag-handles/column/plugin";
import { TableRowDragHandlePlugin } from "../plugins/drag-handles/row/plugin";
import { TableInsertPlugin } from "../plugins/insert-handlers/plugin";
import { TableExtensionConfig } from "./extension-config";
import { TableView } from "./table-view";

export const Table = TableExtensionConfig.extend({
  addNodeView() {
    return ({ editor, node, decorations, getPos }) => {
      const { cellMinWidth } = this.options;

      return new TableView(node, cellMinWidth, decorations, editor, getPos);
    };
  },

  addProseMirrorPlugins() {
    const isResizable = this.options.resizable && this.editor.isEditable;

    const plugins = [
      tableEditing({
        allowTableNodeSelection: this.options.allowTableNodeSelection,
      }),
      TableDragStatePlugin,
      TableInsertPlugin(this.editor),
      TableColumnDragHandlePlugin(this.editor),
      TableRowDragHandlePlugin(this.editor),
    ];

    if (isResizable) {
      plugins.unshift(
        columnResizing({
          handleWidth: this.options.handleWidth,
          cellMinWidth: this.options.cellMinWidth,
          // View: TableView,
          lastColumnResizable: this.options.lastColumnResizable,
        })
      );
    }

    return plugins;
  },
});
