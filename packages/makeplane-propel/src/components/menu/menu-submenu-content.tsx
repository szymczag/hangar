import { MenuContentSurface, type MenuSurfaceProps } from "./menu-content.shared";

export type MenuSubmenuContentProps = Omit<MenuSurfaceProps, "side" | "sizing"> & {
  /** Which side of the parent row the submenu opens toward. @default "right" */
  side?: MenuSurfaceProps["side"];
  /**
   * How the submenu popup takes its width — the same rule as `MenuContent`: `auto` is the content's
   * width between the 204px floor and the 400px ceiling, held while open; `anchor` matches the
   * parent row's width.
   *
   * @default "auto"
   */
  sizing?: MenuSurfaceProps["sizing"];
};

/**
 * The floating surface for a submenu — the same elevated, scrollable panel as `MenuContent`, but
 * anchored beside its parent row instead of below a trigger. Place it inside a `MenuSubmenu`,
 * alongside the `MenuSubmenuTrigger` that opens it.
 */
export function MenuSubmenuContent({
  side = "right",
  sideOffset = 4,
  align = "start",
  sizing = "auto",
  ...props
}: MenuSubmenuContentProps) {
  return (
    <MenuContentSurface
      side={side}
      sideOffset={sideOffset}
      align={align}
      sizing={sizing}
      {...props}
    />
  );
}
