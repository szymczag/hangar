import { Drawer as BaseDrawer } from "@base-ui/react/drawer";

export type DrawerProps = Omit<
  BaseDrawer.Root.Props,
  "className" | "style" | "modal" | "swipeDirection"
> & {
  /**
   * Modal while open. Off by default so inline/layout drawers keep the page interactive. Pass
   * `true` or `"trap-focus"` for blocking overlays (typically with `DrawerPanel backdrop`).
   *
   * @default false
   */
  modal?: BaseDrawer.Root.Props["modal"];
  /**
   * Swipe-to-dismiss direction. Pair with `DrawerPanel` `side`: `"end"` → `"right"`, `"start"` →
   * `"left"`. Base UI defaults this to `"down"` (vertical), which is wrong for horizontal edge
   * drawers — set it explicitly.
   */
  swipeDirection?: BaseDrawer.Root.Props["swipeDirection"];
};

/**
 * The drawer Root that holds open state and gesture configuration. Uncontrolled by default; pass
 * `defaultOpen` (uncontrolled) or `open` + `onOpenChange` (controlled).
 *
 * A behavior-only role that renders no element of its own (rules 1a, 2), so it lives in
 * `components`; the styled parts live in `elements/drawer` and are grafted onto Base UI behavior
 * here.
 */
export function Drawer({ modal = false, ...props }: DrawerProps) {
  return <BaseDrawer.Root modal={modal} {...props} />;
}
