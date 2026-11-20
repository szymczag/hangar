import {
  ComboboxCheckboxItemIndicator,
  ComboboxItemContent,
  ComboboxItemControl,
  ComboboxItemTitle,
  ComboboxSelectAll as ComboboxSelectAllElement,
} from "../../elements/combobox";
import { TickOutline, MinusOutline } from "../../icons";

export type ComboboxSelectAllProps = {
  /**
   * Visible row label.
   *
   * @default "Select all"
   */
  label?: string;
  /** Whether every item is currently selected. */
  checked: boolean;
  /**
   * Whether only some (not all) items are currently selected — shows a dash instead of a check.
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
 * Sticky "select every item" row for a multi-select combobox panel. Not a `ComboboxItem` — it is
 * not a list option — so compose it in `ComboboxContent`'s `search` slot above the scrolling list.
 */
export function ComboboxSelectAll({
  label = "Select all",
  checked,
  indeterminate = false,
  disabled,
  onClick,
}: ComboboxSelectAllProps) {
  return (
    <ComboboxSelectAllElement
      disabled={disabled}
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      data-selected={checked ? "" : undefined}
      data-indeterminate={indeterminate ? "" : undefined}
      data-disabled={disabled ? "" : undefined}
      // Keep focus where it was. This row sits in the panel HEADER, outside
      // `store.state.listElement` — and `Combobox.Popup`'s `onFocus` only bounces focus back to the
      // input for targets inside the list or the popup itself, so without this a click parks focus
      // on the button and typing / Arrow Up / Arrow Down stop reaching the combobox until the user
      // clicks the search field again. Base UI's own `Combobox.Clear` does exactly this.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
    >
      <ComboboxItemControl>
        <ComboboxCheckboxItemIndicator
          data-selected={checked ? "" : undefined}
          data-indeterminate={indeterminate ? "" : undefined}
        >
          {indeterminate ? <MinusOutline aria-hidden /> : <TickOutline aria-hidden />}
        </ComboboxCheckboxItemIndicator>
      </ComboboxItemControl>
      <ComboboxItemContent>
        <ComboboxItemTitle>{label}</ComboboxItemTitle>
      </ComboboxItemContent>
    </ComboboxSelectAllElement>
  );
}
