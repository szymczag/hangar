import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { suggestionMenuItemIconVariants } from "./variants";

export type SuggestionMenuItemIconProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The row's leading glyph slot. Sizes its child to 16px and tints it `icon-secondary`. Decorative:
 * renders with `aria-hidden`.
 */
export function SuggestionMenuItemIcon({ render, ...props }: SuggestionMenuItemIconProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: suggestionMenuItemIconVariants(),
    "aria-hidden": true,
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
