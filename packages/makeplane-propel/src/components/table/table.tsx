import { ScrollArea as BaseScrollArea } from "@base-ui/react/scroll-area";

import { ScrollAreaCorner, ScrollAreaScrollbar, ScrollAreaThumb } from "../../elements/scroll-area";
import {
  Table as TableElement,
  type TableProps as TableElementProps,
  TableScrollArea,
  type TableVariant,
  TableScrollAreaViewport,
} from "../../elements/table";
import { TableVariantContext } from "./table-context";

export type TableProps = TableElementProps & {
  /**
   * Layout (required). `table` draws a rounded frame with row dividers only; `spreadsheet` draws
   * the same frame with a full grid; `plain` drops the frame and the fills, leaving row dividers on
   * the host surface. Its sticky header and pinned cells paint `surface-1`; on any other surface,
   * set the `--table-surface` CSS custom property on an ancestor to that surface's fill.
   */
  variant: TableVariant;
};

/**
 * The ready-made table: the styled `<table>` wrapped in a scroll frame (rounded and
 * hairline-bordered, or bare for `variant="plain"`), sharing its layout `variant` with the
 * rows/cells/heads via context. The Base UI `ScrollArea` behavior grafts onto the styled
 * `TableScrollArea` frame + viewport (and the overlay scrollbars) via `render`, behavior part
 * outer.
 */
export function Table({ variant, ...props }: TableProps) {
  return (
    <TableVariantContext.Provider value={variant}>
      <BaseScrollArea.Root render={<TableScrollArea variant={variant} />}>
        <BaseScrollArea.Viewport render={<TableScrollAreaViewport />}>
          <TableElement {...props} />
        </BaseScrollArea.Viewport>
        <BaseScrollArea.Scrollbar orientation="vertical" render={<ScrollAreaScrollbar />}>
          <BaseScrollArea.Thumb render={<ScrollAreaThumb />} />
        </BaseScrollArea.Scrollbar>
        <BaseScrollArea.Scrollbar orientation="horizontal" render={<ScrollAreaScrollbar />}>
          <BaseScrollArea.Thumb render={<ScrollAreaThumb />} />
        </BaseScrollArea.Scrollbar>
        <BaseScrollArea.Corner render={<ScrollAreaCorner />} />
      </BaseScrollArea.Root>
    </TableVariantContext.Provider>
  );
}
