import {
  ContextMenuContentSurface,
  type ContextMenuSurfaceProps,
} from "./context-menu-content.shared";

export type ContextMenuSubmenuContentProps = Omit<ContextMenuSurfaceProps, "sizing"> & {
  /**
   * How the submenu popup takes its width — the same rule as `ContextMenuContent`: `auto` is the
   * content's width between the 204px floor and the 400px ceiling, held while open; `anchor`
   * matches the parent row's width.
   *
   * @default "auto"
   */
  sizing?: ContextMenuSurfaceProps["sizing"];
};

/**
 * The floating surface for a submenu — the same elevated, scrollable panel as `ContextMenuContent`,
 * anchored beside its parent row instead of at the pointer. Place it inside a `ContextMenuSubmenu`,
 * alongside the `ContextMenuSubmenuTrigger` that opens it.
 */
export function ContextMenuSubmenuContent({
  sizing = "auto",
  ...props
}: ContextMenuSubmenuContentProps) {
  return <ContextMenuContentSurface sizing={sizing} {...props} />;
}
