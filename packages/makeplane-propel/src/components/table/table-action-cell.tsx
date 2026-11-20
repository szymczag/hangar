import type { MenuRoot } from "@base-ui/react/menu";
import type * as React from "react";

import {
  TableCell,
  type TableCellProps,
  TableCellTrigger,
  TableCellTriggerIndicator,
  type TablePinned,
} from "../../elements/table/index";
import { MoreHorizontalOutline } from "../../icons";
import { Menu, MenuTrigger } from "../menu";
import { useTableVariant } from "./table-context";

export type TableActionCellProps = Omit<
  TableCellProps,
  "padding" | "pinned" | "children" | "variant"
> & {
  /** The menu of row actions. */
  children: React.ReactNode;
  /**
   * Which inline edge this cell pins to while the table scrolls sideways. Pin the matching
   * `TableHead` the same way — nothing derives it.
   *
   * @default "none"
   */
  pinned?: TablePinned;
  /** Accessible name for the trigger (e.g. "Row options"). Required (icon-only). */
  "aria-label": string;
  /** Trigger glyph. @default an ellipsis. */
  icon?: React.ReactNode;
  /** Whether the menu is open (controlled). Pair with `onOpenChange`. */
  open?: boolean;
  /** Default open state for an uncontrolled cell. @default false */
  defaultOpen?: boolean;
  /** Called when the menu requests to open or close. */
  onOpenChange?: MenuRoot.Props["onOpenChange"];
  /** Disables the trigger. */
  disabled?: boolean;
};

/** An icon-only action cell (`<td>`) that opens a row-actions menu. */
export function TableActionCell({
  children,
  "aria-label": ariaLabel,
  icon,
  pinned = "none",
  open,
  defaultOpen,
  onOpenChange,
  disabled,
  ...props
}: TableActionCellProps) {
  const variant = useTableVariant();
  return (
    <TableCell variant={variant} pinned={pinned} padding="trigger" {...props}>
      <Menu open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        <MenuTrigger
          disabled={disabled}
          aria-label={ariaLabel}
          render={<TableCellTrigger layout="action" />}
        >
          <TableCellTriggerIndicator>{icon ?? <MoreHorizontalOutline />}</TableCellTriggerIndicator>
        </MenuTrigger>
        {children}
      </Menu>
    </TableCell>
  );
}
