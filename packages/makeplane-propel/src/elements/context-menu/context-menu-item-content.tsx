import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { contextMenuItemContentVariants } from "./variants";

export type ContextMenuItemContentProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The text column of a stacked row. Grows to fill the row so trailing regions sit at the
 * inline-end, and stacks a `ContextMenuItemLabel` over a `ContextMenuItemDescription`.
 * Base-UI-agnostic.
 */
export function ContextMenuItemContent({ render, ...props }: ContextMenuItemContentProps) {
  const defaultProps: useRender.ElementProps<"span"> & { "data-slot": string } = {
    className: contextMenuItemContentVariants(),
    "data-slot": "menu-item-content",
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
