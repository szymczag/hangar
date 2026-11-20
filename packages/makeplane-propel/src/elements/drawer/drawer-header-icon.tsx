import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { drawerHeaderIconVariants } from "./variants";

export type DrawerHeaderIconProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * Decorative leading glyph beside the title inside `DrawerHeaderStart`. Sizes a bare svg/img child;
 * interactive leading controls should be an `IconButton` instead. Bakes `aria-hidden`.
 */
export function DrawerHeaderIcon({ render, ...props }: DrawerHeaderIconProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: drawerHeaderIconVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
