import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectItemTrailingVariants } from "./variants";

export type SelectItemTrailingProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * A slot at a row's inline-end for arbitrary content (a count, a badge). Sizes an icon child to the
 * row's `--node-size`.
 */
export function SelectItemTrailing({ render, ...props }: SelectItemTrailingProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: selectItemTrailingVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
