import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxCheckboxItemIndicatorVariants } from "./variants";

export type ComboboxCheckboxItemIndicatorProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The styled checkbox BOX shown at the leading edge of a multi-select combobox item (16px
 * hit-target, 14px inset chrome that fills the accent on `data-selected`; its glyph child stays
 * hidden until selected). Base-UI-agnostic — graft the indicator behavior in `components` via
 * `<BaseCombobox.ItemIndicator keepMounted render={<ComboboxCheckboxItemIndicator />} />`.
 */
export function ComboboxCheckboxItemIndicator({
  render,
  ...props
}: ComboboxCheckboxItemIndicatorProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: comboboxCheckboxItemIndicatorVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
