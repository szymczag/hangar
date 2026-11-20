import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { suggestionMenuItemTrailingVariants } from "./variants";

export type SuggestionMenuItemTrailingProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** The slot at the row's inline-end, e.g. a plan badge. Sizes an icon child; keeps its own color. */
export function SuggestionMenuItemTrailing({ render, ...props }: SuggestionMenuItemTrailingProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: suggestionMenuItemTrailingVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
