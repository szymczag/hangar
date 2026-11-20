import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ContextMenuItemVariantProps, contextMenuItemVariants } from "./variants";

export type ContextMenuRadioItemProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  ContextMenuItemVariantProps;

/**
 * The styled radio menu row. Base-UI-agnostic — graft the radio-item behavior in `components` via
 * `<BaseContextMenu.RadioItem render={<ContextMenuRadioItem/>} />`.
 */
export function ContextMenuRadioItem({ variant, render, ...props }: ContextMenuRadioItemProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: contextMenuItemVariants({ variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
