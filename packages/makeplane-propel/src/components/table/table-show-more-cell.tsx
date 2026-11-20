import type * as React from "react";

import {
  TableCell as TableCellElement,
  type TableCellProps as TableCellElementProps,
  TableCellLayout,
  TableExpandSpacer,
} from "../../elements/table/index";
import { TextButton } from "../text-button";
import { useTableVariant } from "./table-context";

export type TableShowMoreCellProps = Omit<
  TableCellElementProps,
  "children" | "variant" | "padding" | "onClick"
> & {
  /** The button text, e.g. `"Show 16 more"`. */
  label: string;
  /** Called when the button is activated. */
  onClick?: React.MouseEventHandler<HTMLElement>;
  /**
   * Nesting level of the rows this button reveals more of, so it lines up with their content.
   *
   * @default 1
   */
  depth?: number;
};

/**
 * A cell (`<td>`) holding a text button that reveals the rest of a long run of nested rows. Put it
 * alone in a `TableRow` after the nested rows shown so far, and pass `colSpan` so it spans the
 * table. It is indented to line up with the nested rows' content.
 *
 * Like the expand control, activating the button does not reach the row: its click, and the Enter
 * or Space keydown that activates it, stop at the button, so an `interactive` row's own handler
 * does not also fire.
 *
 * The cell does not count rows: the consumer decides how many nested rows to render first and what
 * the label says.
 */
export function TableShowMoreCell({ label, onClick, depth = 1, ...props }: TableShowMoreCellProps) {
  const variant = useTableVariant();
  return (
    <TableCellElement variant={variant} {...props}>
      <TableCellLayout depth={depth}>
        <TableExpandSpacer />
        <TextButton
          variant="secondary"
          size="md"
          label={label}
          onClick={(event) => {
            event.stopPropagation();
            onClick?.(event);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") event.stopPropagation();
          }}
        />
      </TableCellLayout>
    </TableCellElement>
  );
}
