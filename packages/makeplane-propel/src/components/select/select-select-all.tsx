import {
  SelectCheckboxItemIndicator,
  SelectItemContent,
  SelectItemText,
  SelectItemTitleRow,
  SelectSelectAll as SelectSelectAllElement,
} from "../../elements/select";
import { TickOutline, MinusOutline } from "../../icons";

export type SelectSelectAllProps = {
  /**
   * Visible row label.
   *
   * @default "Select all"
   */
  label?: string;
  /** Whether every option is currently selected. */
  checked: boolean;
  /**
   * Whether only some (not all) options are currently selected — shows a dash instead of a check.
   * Takes precedence over `checked` for both the glyph and `aria-checked="mixed"`.
   *
   * @default false
   */
  indeterminate?: boolean;
  /** Disables the row. */
  disabled?: boolean;
  /** Called when the row is activated. */
  onClick: () => void;
};

/**
 * Sticky "select every option" row for a `multiple` select, the counterpart of `ComboboxSelectAll`.
 * Not a `SelectItem` — it is not an option — so compose it in `SelectContent`'s `header` (inside a
 * `SelectStickyList`) above the scrolling list, and wire `checked` / `indeterminate` / `onClick` to
 * the select's controlled `value`.
 */
export function SelectSelectAll({
  label = "Select all",
  checked,
  indeterminate = false,
  disabled,
  onClick,
}: SelectSelectAllProps) {
  return (
    <SelectSelectAllElement
      // Out of the tab order: Base UI's focus manager focuses the popup's first TABBABLE element
      // on open, and the options are not tabbable (Base UI moves focus between them itself), so a
      // tabbable header row would take the initial focus from the list — Space would then toggle
      // Select all and a screen reader would land on a checkbox instead of an option.
      tabIndex={-1}
      disabled={disabled}
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      data-disabled={disabled ? "" : undefined}
      // Keep focus where it was. This row sits in the panel HEADER, outside Base UI's list, so a
      // click would otherwise park focus on the button and Arrow Up / Arrow Down would stop moving
      // the highlight through the options until the user clicked back into the list.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    >
      <SelectCheckboxItemIndicator
        data-selected={checked ? "" : undefined}
        data-indeterminate={indeterminate ? "" : undefined}
      >
        {indeterminate ? <MinusOutline aria-hidden /> : <TickOutline aria-hidden />}
      </SelectCheckboxItemIndicator>
      <SelectItemContent>
        <SelectItemTitleRow>
          <SelectItemText>{label}</SelectItemText>
        </SelectItemTitleRow>
      </SelectItemContent>
    </SelectSelectAllElement>
  );
}
