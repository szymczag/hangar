import { SkeletonItem } from "../../elements/skeleton";
import {
  TableCell,
  type TableCellProps,
  type TableCellPadding,
  type TablePinned,
} from "../../elements/table/index";
import { useTableVariant } from "./table-context";

export type TableSkeletonCellProps = Omit<TableCellProps, "children" | "variant"> & {
  /**
   * CSS inline size of the placeholder bar, e.g. `"60%"` or `"80px"`. Omit to fill the column. Vary
   * it per column to sketch the loaded table's rhythm rather than a wall of full-width bars.
   */
  inlineSize?: string;
  /** CSS block size of the bar. Omit for one text line. */
  blockSize?: string;
  /** Which inline edge this cell pins to, so a pinned column keeps its pin while loading. */
  pinned?: TablePinned;
  /** Padding, matching the real cell this stands in for. */
  padding?: TableCellPadding;
};

/**
 * A placeholder data cell: a real `<td>` — same borders, same 44px row, same column — holding one
 * decorative bar, so the loading table has the geometry of the table it is standing in for.
 *
 * There is no `align`: `align` positions text inside the content region, and a bar is a block box
 * that `text-align` does not move. Size it with `inlineSize` instead. `SkeletonItem` bakes its own
 * `aria-hidden` — the `TableSkeletonBody` around it carries the accessible name.
 */
export function TableSkeletonCell({ inlineSize, blockSize, ...props }: TableSkeletonCellProps) {
  const variant = useTableVariant();
  return (
    <TableCell variant={variant} {...props}>
      <SkeletonItem blockSize={blockSize} inlineSize={inlineSize} />
    </TableCell>
  );
}
