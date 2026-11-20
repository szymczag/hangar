import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxItemTrailingVariants } from "./variants";

export type ComboboxItemTrailingProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The slot at a row's inline-end for arbitrary trailing content (a count, an icon). Sizes any icon
 * child to the row's `--node-size`.
 */
export function ComboboxItemTrailing({ render, ...props }: ComboboxItemTrailingProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: comboboxItemTrailingVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
