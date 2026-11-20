import {
  TableRow as TableRowElement,
  type TableRowProps as TableRowElementProps,
} from "../../elements/table/index";
import { useTableVariant } from "./table-context";

export type TableRowProps = Omit<TableRowElementProps, "variant">;

/**
 * A ready-made table row (`<tr>`), taking its resting fill from the surrounding `Table`'s
 * `variant`. `selected` paints the selected tint, `interactive` marks the row as a click target,
 * and `section` makes it a non-data row that labels the rows beneath it.
 *
 * `selected` is a visual state only. Pair it with a `TableSelectCell`, whose checkbox carries the
 * real state.
 */
export function TableRow(props: TableRowProps) {
  const variant = useTableVariant();
  return <TableRowElement variant={variant} {...props} />;
}
