import { NavigationMenu as BaseNavigationMenu } from "@base-ui/react/navigation-menu";

import {
  NavigationMenuPopup,
  type NavigationMenuPopupProps,
} from "../../elements/navigation-menu/navigation-menu-popup";
import { Positioner } from "../../internal/positioner";

export type NavigationMenuPanelProps = NavigationMenuPopupProps & {
  /** Which side of the trigger the panel opens toward. @default "bottom" */
  side?: BaseNavigationMenu.Positioner.Props["side"];
  /** Distance in px between the trigger and the panel. @default 4 */
  sideOffset?: BaseNavigationMenu.Positioner.Props["sideOffset"];
  /** Alignment of the panel relative to the trigger along `side`. @default "start" */
  align?: BaseNavigationMenu.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the panel along the trigger's edge
   * without changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseNavigationMenu.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the panel and the viewport edge it would otherwise touch.
   *
   * @default 5
   */
  collisionPadding?: BaseNavigationMenu.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the panel is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseNavigationMenu.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the panel would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseNavigationMenu.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the panel on screen after the trigger scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BaseNavigationMenu.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. a
   * menubar inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BaseNavigationMenu.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the trigger — an element, a ref, a virtual element, or
   * a function returning one. Geometry only; the trigger keeps its role and interactions.
   */
  anchor?: BaseNavigationMenu.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseNavigationMenu.Positioner.Props["disableAnchorTracking"];
};

/**
 * The navigation menu surface: Base UI portal + positioner + popup grafted onto Propel styling.
 * Named `Panel` to avoid clashing with Base UI's atomic per-item `NavigationMenu.Content`. The
 * viewport and per-item content remain children.
 */
export function NavigationMenuPanel({
  side = "bottom",
  sideOffset = 4,
  align = "start",
  alignOffset,
  collisionPadding,
  collisionBoundary,
  collisionAvoidance,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  ...props
}: NavigationMenuPanelProps) {
  return (
    <BaseNavigationMenu.Portal>
      <BaseNavigationMenu.Positioner
        side={side}
        sideOffset={sideOffset}
        align={align}
        alignOffset={alignOffset}
        collisionPadding={collisionPadding}
        collisionBoundary={collisionBoundary}
        collisionAvoidance={collisionAvoidance}
        sticky={sticky}
        positionMethod={positionMethod}
        anchor={anchor}
        disableAnchorTracking={disableAnchorTracking}
        render={<Positioner />}
      >
        <BaseNavigationMenu.Popup {...props} render={<NavigationMenuPopup />} />
      </BaseNavigationMenu.Positioner>
    </BaseNavigationMenu.Portal>
  );
}
