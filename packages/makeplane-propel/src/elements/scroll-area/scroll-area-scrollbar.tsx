import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { scrollAreaScrollbarVariants, type ScrollAreaScrollbarVariantProps } from "./variants";

export type { ScrollAreaScrollbarSize, ScrollAreaScrollbarVisibility } from "./variants";

export type ScrollAreaScrollbarProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  ScrollAreaScrollbarVariantProps;

/**
 * The styled scrollbar track. Base-UI-agnostic — graft in `components` via
 * `<BaseScrollArea.Scrollbar render={<ScrollAreaScrollbar/>} />` (the Base UI Scrollbar sets the
 * `data-orientation`/`data-hovering`/`data-scrolling` state the cva reads).
 *
 * @param visibility — When the rail shows. @default "auto"
 * @param size — Gutter scale. @default "md"
 */
export function ScrollAreaScrollbar({
  visibility,
  size,
  render,
  ...props
}: ScrollAreaScrollbarProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: scrollAreaScrollbarVariants({ visibility, size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
