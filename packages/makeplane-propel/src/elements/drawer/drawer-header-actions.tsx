import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type DrawerHeaderActionsVariantProps, drawerHeaderActionsVariants } from "./variants";

export type { DrawerHeaderActionsSide } from "./variants";

export type DrawerHeaderActionsProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  DrawerHeaderActionsVariantProps;

/**
 * Header icon-button toolbar. `side="start"` / `side="end"` pin the cluster to the header's inline
 * edges (Figma top-left / top-right sockets). Pass `IconButton`s and/or `DrawerClose`.
 */
export function DrawerHeaderActions({ side, render, ...props }: DrawerHeaderActionsProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerHeaderActionsVariants({ side }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
