import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { suggestionMenuGroupVariants } from "./variants";

export type SuggestionMenuGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** A section of rows. Consecutive sections are divided by a hairline; the last draws none. */
export function SuggestionMenuGroup({ render, ...props }: SuggestionMenuGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: suggestionMenuGroupVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
