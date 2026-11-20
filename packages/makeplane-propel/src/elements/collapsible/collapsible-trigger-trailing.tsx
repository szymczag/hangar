import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  collapsibleTriggerTrailingVariants,
  type CollapsibleTriggerTrailingVariantProps,
} from "./variants";

export type CollapsibleTriggerTrailingProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  CollapsibleTriggerTrailingVariantProps;

/**
 * Inline-end slot for a header action, sibling of `CollapsibleTrigger` — never nested inside it
 * (the trigger is a button). Typical content is an `IconButton`. End padding matches the panel
 * inset so the control lines up with the body.
 */
export function CollapsibleTriggerTrailing({
  placement,
  render,
  ...props
}: CollapsibleTriggerTrailingProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: collapsibleTriggerTrailingVariants({ placement }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}

export type { CollapsibleTriggerTrailingPlacement } from "./variants";
