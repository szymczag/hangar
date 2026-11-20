import { Combobox as BaseCombobox } from "@base-ui/react/combobox";

import { ComboboxItemIndicator as ComboboxItemIndicatorElement } from "../../elements/combobox";
import { TickOutline } from "../../icons";

export type ComboboxItemIndicatorProps = Omit<
  BaseCombobox.ItemIndicator.Props,
  "className" | "style"
>;

/**
 * Ready-made combobox item indicator: Base UI's selection behavior grafted onto the styled marker,
 * with a default check when no children are given (defaults are a `components` concern). Composed
 * at the row's inline-end. Mounted on every row by default, so a selection change never
 * re-truncates a label and the reserved column holds while unselected (the styled marker hides its
 * glyph off `data-selected`).
 */
export function ComboboxItemIndicator({ children, ...props }: ComboboxItemIndicatorProps) {
  return (
    <BaseCombobox.ItemIndicator keepMounted {...props} render={<ComboboxItemIndicatorElement />}>
      {children ?? <TickOutline aria-hidden />}
    </BaseCombobox.ItemIndicator>
  );
}
