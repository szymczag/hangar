import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { contextMenuRadioItemCheckVariants } from "./variants";

export type ContextMenuRadioItemCheckProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The styled selection region of a radio menu row. Sizes its single child (the selection icon) to
 * the row's `--node-size`. Base-UI-agnostic — graft in `components` via
 * `<BaseContextMenu.RadioItemIndicator render={<ContextMenuRadioItemCheck/>} />`.
 */
export function ContextMenuRadioItemCheck({ render, ...props }: ContextMenuRadioItemCheckProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: contextMenuRadioItemCheckVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
