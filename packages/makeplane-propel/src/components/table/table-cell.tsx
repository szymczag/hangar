import type * as React from "react";

import {
  type TableAlign,
  TableCell as TableCellElement,
  type TableCellProps as TableCellElementProps,
  TableCellContent,
  TableCellLayout,
} from "../../elements/table/index";
import { NodeSlot } from "../../internal/node-slot";
import { useTableVariant } from "./table-context";

export type TableCellProps = Omit<TableCellElementProps, "children" | "variant"> & {
  /** Leading element beside the cell text, e.g. `<Icon icon={...} />` or an `Avatar`. */
  startIcon?: React.ReactNode;
  /** Trailing element beside the cell text, e.g. `<Icon icon={...} />` or an `Avatar`. */
  endIcon?: React.ReactNode;
  /** Cell content. */
  children?: React.ReactNode;
  /**
   * Column alignment. Pair it with the same `align` on this column's `TableHead`. It moves the text
   * inside the growing content region, so the leading and trailing slots keep their edges.
   *
   * @default "start"
   */
  align?: TableAlign;
};

/** A ready-made data cell: optional leading/trailing slots around a truncating content region. */
export function TableCell({ startIcon, endIcon, children, align, ...props }: TableCellProps) {
  const variant = useTableVariant();
  return (
    <TableCellElement variant={variant} {...props}>
      <TableCellLayout>
        {startIcon != null ? <NodeSlot>{startIcon}</NodeSlot> : null}
        <TableCellContent align={align}>{children}</TableCellContent>
        {endIcon != null ? <NodeSlot>{endIcon}</NodeSlot> : null}
      </TableCellLayout>
    </TableCellElement>
  );
}
