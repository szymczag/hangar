import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxItemContentVariants } from "./variants";

export type ComboboxItemContentProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** The text column of a row. Grows to fill the row so trailing nodes sit at the inline-end. */
export function ComboboxItemContent({ render, ...props }: ComboboxItemContentProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: comboboxItemContentVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
