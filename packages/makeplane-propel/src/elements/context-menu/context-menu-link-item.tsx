import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ContextMenuItemVariantProps, contextMenuItemVariants } from "./variants";

export type ContextMenuLinkItemProps = Omit<useRender.ComponentProps<"a">, "className" | "style"> &
  ContextMenuItemVariantProps;

/**
 * The styled navigational `<a>` menu row. Base-UI-agnostic — graft the link-item behavior in
 * `components` via `<BaseContextMenu.LinkItem render={<ContextMenuLinkItem/>} />`.
 */
export function ContextMenuLinkItem({ variant, render, ...props }: ContextMenuLinkItemProps) {
  const defaultProps: useRender.ElementProps<"a"> = {
    className: contextMenuItemVariants({ variant }),
  };
  return useRender({ defaultTagName: "a", render, props: mergeProps(defaultProps, props) });
}
