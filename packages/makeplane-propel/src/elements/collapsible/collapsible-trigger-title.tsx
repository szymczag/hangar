import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  collapsibleTriggerTitleVariants,
  type CollapsibleTriggerTitleVariantProps,
} from "./variants";

export type CollapsibleTriggerTitleProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
> &
  CollapsibleTriggerTitleVariantProps;

/**
 * The trigger's label. Packed beside an optional leading icon and the disclosure caret (Figma
 * clusters `[icon?][title][chevron]` — the title does not grow to push the caret trail-end). A
 * header trailing action sits outside the trigger, as a sibling. Long labels wrap (`min-w-0`)
 * rather than Figma's sample `whitespace-nowrap`, matching Accordion.
 */
export function CollapsibleTriggerTitle({
  placement,
  render,
  ...props
}: CollapsibleTriggerTitleProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: collapsibleTriggerTitleVariants({ placement }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}

export type { CollapsibleTriggerTitlePlacement } from "./variants";
