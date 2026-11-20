import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { scrollAreaVariants, type ScrollAreaVariantProps } from "./variants";

export type { ScrollAreaOrientation, ScrollAreaSize, ScrollAreaVariant } from "./variants";

export type ScrollAreaProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ScrollAreaVariantProps;

/**
 * The styled scroll-area root: lays its viewport out as a height-constrained flex column but
 * renders no scrollbars itself. Base-UI-agnostic — graft the scroll behavior in `components` via
 * `<BaseScrollArea.Root render={<ScrollArea/>} />`. The ready-made scroller that composes the
 * viewport, scrollbars, thumb and corner lives in `@makeplane/propel/components/scroll-area`.
 *
 * No `ScrollAreaContent` element: Base UI's optional Content wrapper is omitted (no Figma part;
 * children go in the Viewport). Graft `BaseScrollArea.Content` yourself if you need it.
 *
 * `variant="inset"` pads the root by the `size` track on each `orientation` axis, so the absolutely
 * positioned rails sit in a lane beside the viewport instead of over it. Pass the same `size` and
 * `orientation` as the scrollbars you render.
 */
export function ScrollArea({ variant, size, orientation, render, ...props }: ScrollAreaProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: scrollAreaVariants({ variant, size, orientation }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
