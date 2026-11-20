import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { suggestionMenuItemTitleVariants } from "./variants";

export type SuggestionMenuItemTitleProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** The row label. Grows to fill the row and truncates. */
export function SuggestionMenuItemTitle({ render, ...props }: SuggestionMenuItemTitleProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: suggestionMenuItemTitleVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
