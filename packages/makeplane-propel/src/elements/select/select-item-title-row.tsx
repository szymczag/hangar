import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectItemTitleRowVariants } from "./variants";

export type SelectItemTitleRowProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The baseline-aligned row holding an option's `SelectItemText` label and any
 * `SelectItemSecondaryText`.
 */
export function SelectItemTitleRow({ render, ...props }: SelectItemTitleRowProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: selectItemTitleRowVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
