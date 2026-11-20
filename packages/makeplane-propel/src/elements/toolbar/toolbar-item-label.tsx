import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { toolbarItemLabelVariants } from "./variants";

export type ToolbarItemLabelProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The text label of a toolbar item (e.g. "Comment" on a button, "Text" on a menu trigger). Its own
 * styled `<span>` so the control holds no raw typography. Base-UI-agnostic.
 */
export function ToolbarItemLabel({ render, ...props }: ToolbarItemLabelProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: toolbarItemLabelVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
