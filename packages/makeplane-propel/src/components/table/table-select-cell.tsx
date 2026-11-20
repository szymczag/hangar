import {
  TableCell,
  type TableCellProps,
  TableSelectLayout,
  type TablePinned,
} from "../../elements/table/index";
import { Checkbox } from "../checkbox";
import { useTableVariant } from "./table-context";

export type TableSelectCellProps = Omit<
  TableCellProps,
  "padding" | "pinned" | "children" | "variant"
> & {
  /** Whether this row is selected. */
  checked: boolean;
  /** Called when the box is toggled. */
  onCheckedChange?: (checked: boolean) => void;
  /**
   * Which inline edge this cell pins to while the table scrolls sideways. Pin the matching
   * `TableSelectHead` the same way — nothing derives it.
   *
   * @default "none"
   */
  pinned?: TablePinned;
  /** Disables the box, e.g. a row that cannot be acted on. */
  disabled?: boolean;
  /**
   * Accessible name for the box. Required, because a bare checkbox has no visible text: name it
   * after the row it selects, e.g. `"Select Astra Nova"`.
   */
  "aria-label": string;
};

/**
 * The row-selection cell (`<td>`): a checkbox centred in an unpadded cell, so the whole 44px cell
 * is the pointer target.
 *
 * The checkbox is the semantic source of truth — its own checked state is what assistive tech
 * announces. Pair it with `selected` on the `TableRow` for the row tint, which is decoration.
 */
export function TableSelectCell({
  checked,
  onCheckedChange,
  pinned = "none",
  disabled,
  "aria-label": ariaLabel,
  ...props
}: TableSelectCellProps) {
  const variant = useTableVariant();
  return (
    <TableCell variant={variant} pinned={pinned} padding="trigger" {...props}>
      <TableSelectLayout
        onClick={(event) => {
          // Only a click on the padding around the box: one on the checkbox itself is already
          // handled, and letting it bubble here would toggle twice. A `<label>` would cover the
          // cell more neatly but Base UI's checkbox points its `aria-labelledby` at an ancestor
          // label, which would erase the name passed below.
          if (event.target !== event.currentTarget || disabled) return;
          onCheckedChange?.(!checked);
        }}
      >
        <Checkbox
          checked={checked}
          onCheckedChange={onCheckedChange}
          disabled={disabled}
          aria-label={ariaLabel}
        />
      </TableSelectLayout>
    </TableCell>
  );
}
