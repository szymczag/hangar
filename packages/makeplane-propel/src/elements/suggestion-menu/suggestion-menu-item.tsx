import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { suggestionMenuItemVariants } from "./variants";

export type SuggestionMenuItemProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** A suggestion row. Reads as highlighted when it carries `data-highlighted`. */
export function SuggestionMenuItem({ render, ...props }: SuggestionMenuItemProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: suggestionMenuItemVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
