import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { menuItemContentVariants } from "./variants";

export type MenuItemContentProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The text column of a row. Grows to fill the row so trailing nodes/indicators sit at the
 * inline-end, and stacks a `MenuItemTitleRow` over an optional `MenuItemDescription`.
 */
export function MenuItemContent({ render, ...props }: MenuItemContentProps) {
  const defaultProps: useRender.ElementProps<"span"> & { "data-slot": string } = {
    className: menuItemContentVariants(),
    "data-slot": "menu-item-content",
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
