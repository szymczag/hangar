import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectItemContentVariants } from "./variants";

export type SelectItemContentProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The text column of a row. Grows to fill the row so the check and trailing nodes sit at the
 * inline-end, and stacks a `SelectItemTitleRow` over an optional `SelectItemDescription`.
 */
export function SelectItemContent({ render, ...props }: SelectItemContentProps) {
  const defaultProps: useRender.ElementProps<"span"> & { "data-slot": string } = {
    className: selectItemContentVariants(),
    "data-slot": "menu-item-content",
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
