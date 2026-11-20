import {
  TableHead,
  type TableHeadProps,
  TableSelectLayout,
  type TablePinned,
} from "../../elements/table/index";
import { Checkbox } from "../checkbox";
import { useTableVariant } from "./table-context";

export type TableSelectHeadProps = Omit<
  TableHeadProps,
  "children" | "variant" | "align" | "pinned" | "inset"
> & {
  /**
   * Select-all state. `"indeterminate"` is the partial case — some rows selected, not all — and is
   * what the box shows when a page of rows is partly chosen.
   */
  checked: boolean | "indeterminate";
  /** Called when the select-all box is toggled. */
  onCheckedChange?: (checked: boolean) => void;
  /** Which inline edge this header pins to. Pin the matching `TableSelectCell` the same way. */
  pinned?: TablePinned;
  /** Disables the box, e.g. an empty table. */
  disabled?: boolean;
  /** Accessible name for the box, e.g. `"Select all members"`. Required — the box has no text. */
  "aria-label": string;
};

/**
 * The select-all header cell (`<th>`): a tri-state checkbox centred in the header.
 *
 * `checked="indeterminate"` is a real third state, not a styling flag — it is what a partly
 * selected page must show, and Base UI maps it to `aria-checked="mixed"`.
 */
export function TableSelectHead({
  checked,
  onCheckedChange,
  pinned = "none",
  disabled,
  "aria-label": ariaLabel,
  ...props
}: TableSelectHeadProps) {
  const variant = useTableVariant();
  const indeterminate = checked === "indeterminate";
  return (
    <TableHead variant={variant} pinned={pinned} {...props}>
      <TableSelectLayout
        onClick={(event) => {
          if (event.target !== event.currentTarget || disabled) return;
          onCheckedChange?.(!(checked === true));
        }}
      >
        <Checkbox
          checked={indeterminate ? false : checked}
          indeterminate={indeterminate}
          onCheckedChange={onCheckedChange}
          disabled={disabled}
          aria-label={ariaLabel}
        />
      </TableSelectLayout>
    </TableHead>
  );
}
