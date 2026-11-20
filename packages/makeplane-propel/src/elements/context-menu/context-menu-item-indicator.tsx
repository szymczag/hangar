import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { contextMenuItemIndicatorVariants } from "./variants";

export type ContextMenuItemIndicatorProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The single-select check slot shown at a row's inline-end, after the label and before any trailing
 * node (Figma: icon, then label, then check). A multi-select checkbox keeps the inline-start slot.
 * Decorative (the row carries the selected state), so it is `aria-hidden`. Renders and sizes its
 * single child; pass the glyph as `children`. Base-UI-agnostic.
 */
export function ContextMenuItemIndicator({ render, ...props }: ContextMenuItemIndicatorProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: contextMenuItemIndicatorVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
