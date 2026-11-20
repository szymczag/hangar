import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { expandableSearchRowVariants } from "./variants";

export type ExpandableSearchRowProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The expanded row's width/opacity track — grows from the collapsed trigger's footprint to its own
 * intrinsic width (and back), via the same `data-expanded` boolean the trigger toggles in reverse.
 */
export function ExpandableSearchRow({ render, ...props }: ExpandableSearchRowProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: expandableSearchRowVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
