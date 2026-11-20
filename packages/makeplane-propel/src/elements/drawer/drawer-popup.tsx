import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type DrawerPopupVariantProps, drawerPopupVariants } from "./variants";

export type { DrawerPopupSide, DrawerPopupSize, DrawerPopupVariant } from "./variants";

export type DrawerPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  DrawerPopupVariantProps;

/**
 * The styled sliding panel. `variant` chooses chrome/placement: `inline` flush absolute column,
 * `overlay` / `contained` floating card. Anchored to `side`; slides via Base UI
 * `data-starting-style` / `data-ending-style`. `size` sets width (`sm` 358 / `md` 800 / `lg` 1024).
 * Base-UI-agnostic — graft via `<BaseDrawer.Popup render={<DrawerPopup … />} />`.
 */
export function DrawerPopup({
  side,
  size = "sm",
  variant = "inline",
  render,
  ...props
}: DrawerPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerPopupVariants({ side, size, variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
