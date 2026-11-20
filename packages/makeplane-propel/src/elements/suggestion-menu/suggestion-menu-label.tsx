import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { suggestionMenuLabelVariants } from "./variants";

export type SuggestionMenuLabelProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** A section heading, shown above the section's rows. */
export function SuggestionMenuLabel({ render, ...props }: SuggestionMenuLabelProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: suggestionMenuLabelVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
