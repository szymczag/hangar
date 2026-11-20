import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { menuRadioItemIndicatorVariants } from "./variants";

export type MenuRadioItemIndicatorProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/**
 * The styled radio ring of a radio item — drawn on every row, filling with the accent dot once the
 * row is selected (the same ring the standalone `Radio` draws). Base-UI-agnostic — graft the
 * indicator behavior in `components` via `<BaseMenu.RadioItemIndicator keepMounted
 * render={<MenuRadioItemIndicator />} />`; `keepMounted` is what keeps the empty ring on unselected
 * rows.
 */
export function MenuRadioItemIndicator({ render, ...props }: MenuRadioItemIndicatorProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: menuRadioItemIndicatorVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
