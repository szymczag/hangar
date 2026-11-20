import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ContextMenuPopupVariantProps, contextMenuPopupVariants } from "./variants";

export type { ContextMenuPopupElevation } from "./variants";

export type ContextMenuPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ContextMenuPopupVariantProps;

/**
 * The styled menu surface that contains the items. Base-UI-agnostic — graft the popup behavior in
 * `components` via `<BaseContextMenu.Popup render={<ContextMenuPopup elevation="…" />} />`.
 */
export function ContextMenuPopup({ elevation, render, ...props }: ContextMenuPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: contextMenuPopupVariants({ elevation }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
