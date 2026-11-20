import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { contextMenuItemDescriptionVariants } from "./variants";

export type ContextMenuItemDescriptionProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** A muted second line beneath the label, holding the item's description. Base-UI-agnostic. */
export function ContextMenuItemDescription({ render, ...props }: ContextMenuItemDescriptionProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: contextMenuItemDescriptionVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
