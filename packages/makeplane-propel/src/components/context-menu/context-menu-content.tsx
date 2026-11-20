import {
  ContextMenuContentSurface,
  type ContextMenuSurfaceProps,
} from "./context-menu-content.shared";

export type { ContextMenuContentSizing } from "./context-menu-content.shared";

export type ContextMenuContentProps = Omit<ContextMenuSurfaceProps, "sizing"> & {
  /**
   * How the menu popup is sized — the same rule as `Menu`. `auto` is the content's width between
   * the 204px floor and 400px ceiling, held while open; `anchor` matches the anchor's width
   * instead. The deprecated `menu`/`sm`/`md`/`lg` aliases render as `auto`. The default applies to
   * an omitted _and_ an explicitly `undefined` value.
   *
   * @default "auto"
   */
  sizing?: ContextMenuSurfaceProps["sizing"];
};

/**
 * The root context-menu surface: Base UI's portal and positioner wrapped around an elevated,
 * scrollable `OverlayPanel` holding the flat `role="menu"` popup. Anchors to the pointer and sizes
 * itself like a dropdown. Rows (`ContextMenuItem`, `ContextMenuSeparator`, …) are its children. A
 * submenu's own surface is `ContextMenuSubmenuContent`, not this part.
 */
export function ContextMenuContent({ sizing = "auto", ...props }: ContextMenuContentProps) {
  return <ContextMenuContentSurface sizing={sizing} {...props} />;
}
