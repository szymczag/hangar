import { Drawer as BaseDrawer } from "@base-ui/react/drawer";

import { Backdrop } from "../../internal/backdrop";

export type DrawerBackdropProps = Omit<BaseDrawer.Backdrop.Props, "className" | "style">;

/**
 * The dimmed overlay behind the drawer: Base UI's `Drawer.Backdrop` behavior grafted onto the
 * shared `internal/Backdrop` surface (rule 4a). Fades in/out via Base UI's
 * `data-starting-style`/`data-ending-style` transition hooks.
 *
 * Nested drawers keep their own dim (`forceRender` defaults on): Base UI omits a nested Backdrop
 * unless it is set. Pass `forceRender={false}` to opt out.
 */
export function DrawerBackdrop({ forceRender = true, ...props }: DrawerBackdropProps) {
  return (
    <BaseDrawer.Backdrop
      {...props}
      forceRender={forceRender}
      style={(state) => (state.open ? undefined : { pointerEvents: "none" })}
      render={<Backdrop />}
    />
  );
}
