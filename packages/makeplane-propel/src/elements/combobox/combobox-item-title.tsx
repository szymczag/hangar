import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxItemTitleVariants } from "./variants";

export type ComboboxItemTitleProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/** A row's primary label. Truncates rather than wrapping. */
export function ComboboxItemTitle({ render, ...props }: ComboboxItemTitleProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: comboboxItemTitleVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
