import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type ExpandableSearchTriggerVariantProps,
  expandableSearchTriggerVariants,
} from "./variants";

export type ExpandableSearchTriggerProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
> &
  ExpandableSearchTriggerVariantProps;

/**
 * Centers the collapsed trigger's own (smaller) `IconButton` square inside a box matching the
 * expanded row's height at the same size step, so collapsing/expanding never shifts height.
 */
export function ExpandableSearchTrigger({ size, render, ...props }: ExpandableSearchTriggerProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: expandableSearchTriggerVariants({ size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
