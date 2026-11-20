import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectCheckboxItemIndicatorVariants } from "./variants";

export type SelectCheckboxItemIndicatorProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The styled checkbox BOX shown at the leading edge of a multi-select (`multiple`) select item —
 * the same box a multi-select combobox row draws, filling with the accent on `data-selected`; its
 * glyph child stays hidden until selected. Base-UI-agnostic — graft the indicator behavior in
 * `components` via `<BaseSelect.ItemIndicator keepMounted render={<SelectCheckboxItemIndicator />}
 * />`.
 */
export function SelectCheckboxItemIndicator({
  render,
  ...props
}: SelectCheckboxItemIndicatorProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: selectCheckboxItemIndicatorVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
