import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { scrollAreaViewportVariants, type ScrollAreaViewportVariantProps } from "./variants";

export type ScrollAreaViewportProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ScrollAreaViewportVariantProps;

/**
 * The styled scrollable viewport. Base-UI-agnostic — graft in `components` via
 * `<BaseScrollArea.Viewport render={<ScrollAreaViewport/>} />`. Pass the same `orientation` as the
 * root and its rendered scrollbars: it decides which axes contain overscroll. The `inset` lane is
 * reserved by the root (`ScrollArea`), not here.
 */
export function ScrollAreaViewport({ orientation, render, ...props }: ScrollAreaViewportProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: scrollAreaViewportVariants({ orientation }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
