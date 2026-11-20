import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxSelectAllVariants } from "./variants";

export type ComboboxSelectAllProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style"
>;

/**
 * The styled sticky "Select all" row: a `<button>` with the option row's chrome and its own hover
 * fill (Base UI never highlights it, since it is not an option). The checkbox box, label and
 * checked state are composed in `components` (`ComboboxSelectAll` ready-made).
 */
export function ComboboxSelectAll({ render, ...props }: ComboboxSelectAllProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: comboboxSelectAllVariants(),
    type: "button",
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
