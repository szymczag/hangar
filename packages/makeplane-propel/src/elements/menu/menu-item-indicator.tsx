import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { menuItemIndicatorVariants } from "./variants";

export type MenuItemIndicatorProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The single-select check slot shown at a row's inline-end, after the label and before any
 * `trailing` node (Figma: icon, then label, then check). A multi-select checkbox uses
 * `MenuItemControl` at the inline-start instead. Decorative (the row carries the selected state),
 * so it is `aria-hidden`. Renders and sizes its single child; pass the glyph as `children`.
 */
export function MenuItemIndicator({ render, ...props }: MenuItemIndicatorProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: menuItemIndicatorVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
