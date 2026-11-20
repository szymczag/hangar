import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type MenuRowVariantProps, menuRowVariants } from "./variants";

export type MenuLinkItemProps = Omit<useRender.ComponentProps<"a">, "className" | "style"> &
  Pick<MenuRowVariantProps, "variant">;

/**
 * A styled navigational `<a>` menu row. Base-UI-agnostic — graft the link-item behavior in
 * `components` via `<BaseMenu.LinkItem render={<MenuLinkItem />} />`.
 */
export function MenuLinkItem({ variant, render, ...props }: MenuLinkItemProps) {
  const defaultProps: useRender.ElementProps<"a"> = {
    className: menuRowVariants({ layout: "single", variant }),
  };
  return useRender({ defaultTagName: "a", render, props: mergeProps(defaultProps, props) });
}
