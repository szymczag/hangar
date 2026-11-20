import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type DrawerViewportVariantProps, drawerViewportVariants } from "./variants";

export type { DrawerViewportVariant } from "./variants";

export type DrawerViewportProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  DrawerViewportVariantProps;

/**
 * Positioning layer around the popup. `inline` / `contained` = absolute fill of a portal parent;
 * `overlay` = fixed viewport (body portal). Base-UI-agnostic — graft via `<BaseDrawer.Viewport
 * render={<DrawerViewport variant={…} />} />`.
 */
export function DrawerViewport({ variant = "inline", render, ...props }: DrawerViewportProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerViewportVariants({ variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
