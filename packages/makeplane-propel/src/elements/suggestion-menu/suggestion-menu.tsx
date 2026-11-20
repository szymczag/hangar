import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type SuggestionMenuVariantProps, suggestionMenuVariants } from "./variants";

export type SuggestionMenuProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  SuggestionMenuVariantProps;

/**
 * The popup surface of a suggestion menu. Renders a `<div>`; the `components` ready-made adds the
 * `listbox` role and the keyboard highlight.
 */
export function SuggestionMenu({ width, render, ...props }: SuggestionMenuProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: suggestionMenuVariants({ width }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
