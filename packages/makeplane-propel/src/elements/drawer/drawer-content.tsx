import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type DrawerContentVariantProps, drawerContentVariants } from "./variants";

export type { DrawerContentSize } from "./variants";

export type DrawerContentProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  DrawerContentVariantProps;

/**
 * The styled padded inner content region of the popup. Holds the title, description, body, and
 * close affordances, and allows mouse text selection without triggering swipe-dismiss. Padding
 * follows `size` (`sm` p-4, `md`/`lg` px-8 py-7). Base-UI-agnostic — graft the drawer behavior in
 * `components` via `<BaseDrawer.Content render={<DrawerContent />} />`.
 */
export function DrawerContent({ size = "sm", render, ...props }: DrawerContentProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerContentVariants({ size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
