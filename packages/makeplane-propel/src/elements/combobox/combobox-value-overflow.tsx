import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxValueOverflowVariants } from "./variants";

export type ComboboxValueOverflowProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** Selection summary beside the preview; truncates only when the summary itself cannot fit. */
export function ComboboxValueOverflow({ render, ...props }: ComboboxValueOverflowProps) {
  return useRender({
    defaultTagName: "span",
    render,
    props: mergeProps({ className: comboboxValueOverflowVariants() }, props),
  });
}
