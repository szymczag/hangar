import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxItemControlVariants } from "./variants";

export type ComboboxItemControlProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** The leading control slot of a checkbox row, holding its visual toggle. */
export function ComboboxItemControl({ render, ...props }: ComboboxItemControlProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: comboboxItemControlVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
