import type * as React from "react";

import {
  TableCell as TableCellElement,
  type TableCellProps as TableCellElementProps,
  TableCellContent,
  TableCellLayout,
  TableExpandSpacer,
  TableExpandTrigger,
} from "../../elements/table/index";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";
import { NodeSlot } from "../../internal/node-slot";
import { useTableVariant } from "./table-context";

export type TableExpandCellProps = Omit<
  TableCellElementProps,
  "children" | "variant" | "padding" | "aria-label"
> & {
  /**
   * Leading element beside the cell text, e.g. `<Icon icon={...} />`. It sits after the expand
   * control.
   */
  startIcon?: React.ReactNode;
  /** Cell content. */
  children?: React.ReactNode;
  /**
   * Nesting level of this row. `0` is a top-level row; each level indents the cell by 24px, with no
   * upper limit. Give the rows a parent reveals a `depth` one higher than the parent's.
   *
   * @default 0
   */
  depth?: number;
} & (
    | {
        /**
         * Whether this row's nested rows are showing. Pass it (with `onExpandedChange`) on a row
         * that has nested rows; omit it on a row that has none, which then renders an empty spacer
         * so its content stays aligned with its siblings.
         */
        expanded: boolean;
        /** Called with the next state when the expand control is activated. */
        onExpandedChange: (expanded: boolean) => void;
        /**
         * Accessible name for the expand control. Required, because it has no visible text. Name
         * what it reveals and keep the name the same in both states, e.g. `"Pages nested in
         * Platform Engineering"`. `aria-expanded` already announces the state, so a name that
         * switches between "Expand" and "Collapse" would say it twice.
         */
        "aria-label": string;
      }
    | { expanded?: undefined; onExpandedChange?: undefined; "aria-label"?: undefined }
  );

/**
 * The first cell (`<td>`) of a row in a table with nested rows. With `expanded` it leads with a
 * chevron button that reveals or hides the row's nested rows; without it, with an empty spacer of
 * the same size. `depth` indents the cell for a nested row.
 *
 * The cell owns no state and renders no nested rows. The consumer holds which rows are open and
 * renders the nested `TableRow`s after the parent while it is expanded, the same way it owns the
 * sort order. The table stays a plain `<table>`: the control is a button with `aria-expanded`, and
 * focus stays on it after it is activated.
 *
 * Activating the control does not reach the row: its click, and the Enter or Space keydown that
 * activates it, stop at the control, so an `interactive` row's own click or keyboard handler does
 * not also fire.
 */
export function TableExpandCell({
  startIcon,
  children,
  depth,
  expanded,
  onExpandedChange,
  "aria-label": ariaLabel,
  ...props
}: TableExpandCellProps) {
  const variant = useTableVariant();
  return (
    <TableCellElement variant={variant} {...props}>
      <TableCellLayout depth={depth}>
        {expanded != null ? (
          <TableExpandTrigger
            aria-expanded={expanded}
            aria-label={ariaLabel}
            data-panel-open={expanded ? "" : undefined}
            onClick={(event) => {
              event.stopPropagation();
              onExpandedChange(!expanded);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") event.stopPropagation();
            }}
          >
            <DisclosureIndicator motion="disclose" tint="secondary">
              <ChevronDownOutline />
            </DisclosureIndicator>
          </TableExpandTrigger>
        ) : (
          <TableExpandSpacer />
        )}
        {startIcon != null ? <NodeSlot>{startIcon}</NodeSlot> : null}
        <TableCellContent>{children}</TableCellContent>
      </TableCellLayout>
    </TableCellElement>
  );
}
