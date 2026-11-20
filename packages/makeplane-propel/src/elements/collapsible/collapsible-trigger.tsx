import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { collapsibleTriggerVariants, type CollapsibleTriggerVariantProps } from "./variants";

export type CollapsibleTriggerProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style"
> &
  CollapsibleTriggerVariantProps;

/**
 * The styled disclosure trigger button. Base-UI-agnostic — graft the collapsible behavior in
 * `components` via `<BaseCollapsible.Trigger render={<CollapsibleTrigger/>} />`, which sets
 * `aria-expanded`/`aria-controls` and reflects open state as `[data-panel-open]`.
 */
export function CollapsibleTrigger({ placement, render, ...props }: CollapsibleTriggerProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: collapsibleTriggerVariants({ placement }),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}

export type { CollapsibleTriggerPlacement } from "./variants";
