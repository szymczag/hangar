import { Drawer as BaseDrawer } from "@base-ui/react/drawer";

import { OverlayTitle } from "../../internal/overlay-title";

export type DrawerTitleProps = Omit<BaseDrawer.Title.Props, "className" | "style">;

/**
 * The accessible heading for the drawer: Base UI's `Drawer.Title` behavior (wired as the popup's
 * `aria-labelledby` target) grafted onto the shared `internal/OverlayTitle` at `size="xl"` (body-md
 * semibold per Figma; rule 4a).
 */
export function DrawerTitle(props: DrawerTitleProps) {
  return <BaseDrawer.Title {...props} render={<OverlayTitle size="xl" />} />;
}
