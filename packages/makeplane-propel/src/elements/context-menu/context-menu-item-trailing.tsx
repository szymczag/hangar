import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { contextMenuItemTrailingVariants } from "./variants";

export type ContextMenuItemTrailingProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The slot at a row's inline-end for arbitrary trailing content (a shortcut, a count, a chevron).
 * Sizes any icon child to the row's `--node-size`; unlike an indicator it adds no tint, so passed
 * content keeps its own color.
 */
export function ContextMenuItemTrailing({ render, ...props }: ContextMenuItemTrailingProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: contextMenuItemTrailingVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
