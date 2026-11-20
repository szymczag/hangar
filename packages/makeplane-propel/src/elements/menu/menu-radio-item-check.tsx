import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { menuRadioItemCheckVariants } from "./variants";

export type MenuRadioItemCheckProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The styled TRAILING CHECK of a radio item — the default marker for a single-select group inside a
 * menu, identical to the check every other single-select row uses. Drawn on every row so the gutter
 * column holds; the glyph hides on `data-unchecked`. Base-UI-agnostic — graft in `components` via
 * `<BaseMenu.RadioItemIndicator keepMounted render={<MenuRadioItemCheck />} />`.
 *
 * The ring form (`MenuRadioItemIndicator`) is reserved for a popup that mixes a multi-select group
 * with a single-select one, where the two need telling apart.
 */
export function MenuRadioItemCheck({ render, ...props }: MenuRadioItemCheckProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: menuRadioItemCheckVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
