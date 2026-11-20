import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { tableExpandTriggerVariants } from "./variants";

export type TableExpandTriggerProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style" | "type"
>;

/**
 * The expand control at the start of an expandable row's first cell: a 16px `<button>` holding a
 * caret. It bakes no state: the ready-made `TableExpandCell` sets `aria-expanded`, the accessible
 * name, and `data-panel-open` (which the caret reads to rotate).
 */
export function TableExpandTrigger({ render, ...props }: TableExpandTriggerProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    type: "button",
    className: tableExpandTriggerVariants(),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
