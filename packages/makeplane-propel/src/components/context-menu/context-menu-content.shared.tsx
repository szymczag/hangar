import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";

import { ContextMenuPopup } from "../../elements/context-menu/context-menu-popup";
import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { OverlayPanel, type OverlayPanelSizing } from "../../internal/overlay-panel";
import { Portal } from "../../internal/portal";
import { Positioner } from "../../internal/positioner";

/** Context menus anchor to a pointer rect; the fixed-height sizings are combobox-only. */
export type ContextMenuContentSizing = Exclude<OverlayPanelSizing, "anchor-fixed" | "auto-fixed">;

/**
 * The props both context-menu surfaces share. `sizing` carries no `@default` here: the root and a
 * submenu each declare their own (both `auto` today), so the generated props table documents the
 * default on the part a consumer actually renders rather than on this shared type. `render` is
 * omitted because this surface always grafts the styled `ContextMenuPopup` at `elevation="flat"`
 * inside an `OverlayPanel`, so a consumer-passed `render` would be overwritten and silently do
 * nothing.
 */
export type ContextMenuSurfaceProps = Omit<
  BaseContextMenu.Popup.Props,
  "className" | "style" | "render"
> & {
  /**
   * Which side of the anchor the popup opens toward. Leave it unset at the root: an explicit `side`
   * opts out of Base UI's pointer-hugging offsets, so the menu detaches from the cursor. A submenu
   * opens toward `inline-end` unless told otherwise.
   */
  side?: BaseContextMenu.Positioner.Props["side"];
  /** Distance in px between the anchor and the popup. */
  sideOffset?: BaseContextMenu.Positioner.Props["sideOffset"];
  /** Alignment of the popup relative to the anchor along `side`. */
  align?: BaseContextMenu.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the popup along the anchor's edge without
   * changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseContextMenu.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the popup and the viewport edge it would otherwise touch.
   *
   * @default 16
   */
  collisionPadding?: BaseContextMenu.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the popup is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseContextMenu.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the popup would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseContextMenu.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the popup on screen after its anchor scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BaseContextMenu.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors.
   *
   * @default "absolute"
   */
  positionMethod?: BaseContextMenu.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the pointer — an element, a ref, a virtual element, or
   * a function returning one. Geometry only; right-click targeting is unchanged.
   */
  anchor?: BaseContextMenu.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseContextMenu.Positioner.Props["disableAnchorTracking"];
  /**
   * How the menu popup takes its width. `auto` is the content's width — never narrower than 204px,
   * never wider than 400px or the room beside the pointer, and held while open. `anchor` matches
   * the anchor's width instead, growing only with its content.
   */
  sizing?: ContextMenuContentSizing;
};

export function ContextMenuContentSurface({
  side,
  sideOffset,
  align,
  alignOffset,
  collisionPadding = DROPDOWN_EDGE_GAP_PX,
  collisionBoundary,
  collisionAvoidance,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  sizing,
  ...props
}: ContextMenuSurfaceProps) {
  return (
    <BaseContextMenu.Portal render={<Portal />}>
      <BaseContextMenu.Positioner
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
        <OverlayPanel elevation="overlay" radius="lg" sizing={sizing}>
          <BaseContextMenu.Popup {...props} render={<ContextMenuPopup elevation="flat" />} />
        </OverlayPanel>
      </BaseContextMenu.Positioner>
    </BaseContextMenu.Portal>
  );
}
