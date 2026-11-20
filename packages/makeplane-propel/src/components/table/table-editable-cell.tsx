import type { MenuRoot } from "@base-ui/react/menu";
import type * as React from "react";

import {
  TableCell,
  type TableCellProps,
  TableCellTrigger,
  TableCellTriggerIndicator,
  TableCellTriggerLabel,
  type TablePinned,
} from "../../elements/table/index";
import { ChevronDownOutline } from "../../icons";
import { Menu, MenuTrigger } from "../menu";
import { useTableVariant } from "./table-context";

export type TableEditableCellProps = Omit<
  TableCellProps,
  "padding" | "pinned" | "children" | "variant"
> & {
  /**
   * Which inline edge this cell pins to while the table scrolls sideways. Pin the matching
   * `TableHead` the same way — nothing derives it.
   *
   * @default "none"
   */
  pinned?: TablePinned;
  /** The current value shown in the cell. */
  value: React.ReactNode;
  /** The menu shown when the cell is clicked. */
  children: React.ReactNode;
  /** Whether the menu is open (controlled). */
  open?: boolean;
  /** Default open state for an uncontrolled cell. @default false */
  defaultOpen?: boolean;
  /** Called when the menu requests to open or close. */
  onOpenChange?: MenuRoot.Props["onOpenChange"];
  /** Disables the trigger so the cell can't be edited. */
  disabled?: boolean;
  /**
   * Visual open-menu tint only (`bg-layer-transparent-selected`). Does not set an ARIA selected
   * state — while the menu is open, `aria-expanded` already exposes that. Don't use this for closed
   * cell selection without your own `aria-*`.
   */
  selected?: boolean;
  /**
   * Accessible name for the trigger. Replaces the visible `value` in the name computation — include
   * the current value when you pass this (e.g. `"Account type for Astra: Admin"`).
   */
  "aria-label"?: string;
};

/** An editable data cell (`<td>`) with a full-cell menu trigger. */
export function TableEditableCell({
  pinned = "none",
  value,
  children,
  open,
  defaultOpen,
  onOpenChange,
  disabled,
  selected,
  "aria-label": ariaLabel,
  ...props
}: TableEditableCellProps) {
  const variant = useTableVariant();
  return (
    <TableCell variant={variant} pinned={pinned} padding="trigger" {...props}>
      <Menu open={open} defaultOpen={defaultOpen} onOpenChange={onOpenChange}>
        <MenuTrigger
          disabled={disabled}
          aria-label={ariaLabel}
          render={<TableCellTrigger layout="editable" selected={selected} />}
        >
          <TableCellTriggerLabel>{value}</TableCellTriggerLabel>
          <TableCellTriggerIndicator>
            <ChevronDownOutline />
          </TableCellTriggerIndicator>
        </MenuTrigger>
        {children}
      </Menu>
    </TableCell>
  );
}
