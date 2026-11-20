import { Popover as BasePopover } from "@base-ui/react/popover";

import { PopoverPopup, type PopoverPopupVariant } from "../../elements/popover";
import { Portal } from "../../internal/portal";
import { Positioner } from "../../internal/positioner";

export type { PopoverPopupVariant };

export type PopoverContentProps = Omit<BasePopover.Popup.Props, "className" | "style"> & {
  /**
   * Panel look. `rich` is the padded content panel for forms and arbitrary children; `text` is the
   * compact 296px title + description card.
   *
   * @default "rich"
   */
  variant?: PopoverPopupVariant;
  /**
   * Which side of the trigger the panel opens toward.
   *
   * @default "bottom"
   */
  side?: BasePopover.Positioner.Props["side"];
  /**
   * Alignment of the panel relative to the trigger along `side`.
   *
   * @default "start"
   */
  align?: BasePopover.Positioner.Props["align"];
  /**
   * Distance in px between the trigger and the panel.
   *
   * @default 4
   */
  sideOffset?: BasePopover.Positioner.Props["sideOffset"];
  /**
   * Additional offset in px along the align axis — slides the panel along the trigger's edge
   * without changing `align`.
   *
   * @default 0
   */
  alignOffset?: BasePopover.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the panel and the viewport edge it would otherwise touch.
   *
   * @default 5
   */
  collisionPadding?: BasePopover.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the panel is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BasePopover.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the panel would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BasePopover.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the panel on screen after the trigger scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BasePopover.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. a
   * trigger inside a sticky header. Unset, Base UI uses `absolute`.
   *
   * @default "absolute"
   */
  positionMethod?: BasePopover.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the trigger — an element, a ref, a virtual element, or
   * a function returning one. Geometry only; the trigger keeps its role and interactions.
   */
  anchor?: BasePopover.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BasePopover.Positioner.Props["disableAnchorTracking"];
};

/**
 * A trigger-anchored content panel. Composes the popover portal + positioner + styled popup so a
 * consumer only writes the trigger and the panel body. Pass any trigger through `PopoverTrigger`'s
 * `render`; pass `variant="text"` for the compact title + description card. Put tall `rich` content
 * in `PopoverBody` so it scrolls under the available-height cap.
 */
export function PopoverContent({
  variant,
  side = "bottom",
  align = "start",
  sideOffset = 4,
  alignOffset,
  collisionPadding,
  collisionBoundary,
  collisionAvoidance,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  ...props
}: PopoverContentProps) {
  return (
    <BasePopover.Portal render={<Portal />}>
      <BasePopover.Positioner
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
        <BasePopover.Popup {...props} render={<PopoverPopup variant={variant} />} />
      </BasePopover.Positioner>
    </BasePopover.Portal>
  );
}
