import { PreviewCard as BasePreviewCard } from "@base-ui/react/preview-card";

import {
  PreviewCardPopup,
  type PreviewCardPopupProps,
} from "../../elements/preview-card/preview-card-popup";
import { Positioner } from "../../internal/positioner";

export type PreviewCardContentProps = PreviewCardPopupProps & {
  /** Which side of the trigger the card opens toward. @default "bottom" */
  side?: BasePreviewCard.Positioner.Props["side"];
  /** Distance in px between the trigger and the card. @default 4 */
  sideOffset?: BasePreviewCard.Positioner.Props["sideOffset"];
  /** Alignment of the card relative to the trigger along `side`. @default "center" */
  align?: BasePreviewCard.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the card along the trigger's edge without
   * changing `align`.
   *
   * @default 0
   */
  alignOffset?: BasePreviewCard.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the card and the viewport edge it would otherwise touch.
   *
   * @default 5
   */
  collisionPadding?: BasePreviewCard.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the card is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BasePreviewCard.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the card would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BasePreviewCard.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the card on screen after the trigger scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BasePreviewCard.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. a
   * trigger inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BasePreviewCard.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the trigger — an element, a ref, a virtual element, or
   * a function returning one. Geometry only; the trigger keeps its role and interactions.
   */
  anchor?: BasePreviewCard.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BasePreviewCard.Positioner.Props["disableAnchorTracking"];
};

/**
 * Convenience that composes the anchored preview card boilerplate — Base UI portal, positioner, and
 * popup grafted onto Propel's styled surface — so a consumer only writes the trigger and the card
 * body. Pass `side`/`sideOffset`/`align` through to the positioner.
 *
 * No backdrop: unlike Dialog/AlertDialog/Drawer, a preview card is a non-modal, hover-triggered
 * rich tooltip (it opens on hover/focus and closes on pointer-leave/blur, with no focus trap) —
 * dimming the page behind a hover preview reads as a modal takeover it isn't. Base UI ships a
 * `PreviewCard.Backdrop` primitive, but it is purely optional/decorative for apps that want one; it
 * has none of `Dialog.Backdrop`'s click-outside-to-dismiss semantics, so omitting it costs no
 * behavior.
 */
export function PreviewCardContent({
  side = "bottom",
  sideOffset = 4,
  align = "center",
  alignOffset,
  collisionPadding,
  collisionBoundary,
  collisionAvoidance,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  ...props
}: PreviewCardContentProps) {
  return (
    <BasePreviewCard.Portal>
      <BasePreviewCard.Positioner
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
        <BasePreviewCard.Popup {...props} render={<PreviewCardPopup />} />
      </BasePreviewCard.Positioner>
    </BasePreviewCard.Portal>
  );
}
