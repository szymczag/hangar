import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { expandableSearchTrackVariants } from "./variants";

export type ExpandableSearchTrackProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
>;

/**
 * Stacks the trigger and the row on top of each other so collapsing/expanding grows or shrinks in
 * place, instead of the two rendering as separate sequential boxes. Renders a `div` (flow content)
 * so it can legally wrap the row's own `div`.
 */
export function ExpandableSearchTrack({ render, ...props }: ExpandableSearchTrackProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: expandableSearchTrackVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
