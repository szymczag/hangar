import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { drawerInlinePortalVariants } from "./variants";

export type DrawerInlinePortalProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Styled Base UI portal root for inline drawers. Grafted via `<BaseDrawer.Portal
 * render={<DrawerInlinePortal />} />`. Fills the absolute host / container.
 */
export function DrawerInlinePortal({ render, ...props }: DrawerInlinePortalProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerInlinePortalVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
