import { Combobox as BaseCombobox } from "@base-ui/react/combobox";
import type * as React from "react";

import { ComboboxPopup } from "../../elements/combobox";
import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { OverlayPanel, type OverlayPanelSizing } from "../../internal/overlay-panel";
import { Portal } from "../../internal/portal";
import { Positioner } from "../../internal/positioner";

export type ComboboxContentSizing = OverlayPanelSizing;

/**
 * The props both combobox surfaces share. `side`, `sideOffset`, `align` and `sizing` carry no
 * `@default` here because the two surfaces pick different ones — `ComboboxContent` opens below the
 * field and matches its width, `ComboboxSubmenuContent` opens beside its parent row and sizes
 * itself `auto` — so each declares its own; otherwise the generated props table would advertise one
 * surface's default on both. `render` is omitted because this surface always renders the styled
 * `OverlayPanel`/`ComboboxPopup` pair as the popup's element, so a consumer-passed one would be
 * overwritten and silently do nothing.
 */
export type ComboboxSurfaceProps = Omit<
  BaseCombobox.Popup.Props,
  "className" | "style" | "render"
> & {
  /** Which side of the anchor the list opens toward. */
  side?: BaseCombobox.Positioner.Props["side"];
  /** Distance in px between the anchor and the list. */
  sideOffset?: BaseCombobox.Positioner.Props["sideOffset"];
  /** Alignment of the list relative to the anchor along `side`. */
  align?: BaseCombobox.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the list along the anchor's edge without
   * changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseCombobox.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the list and the viewport edge it would otherwise touch.
   *
   * @default 16
   */
  collisionPadding?: BaseCombobox.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the list is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseCombobox.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the list would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseCombobox.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the list on screen after the anchor scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BaseCombobox.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. an
   * input inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BaseCombobox.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the default anchor — an element, a ref, a virtual
   * element, or a function returning one. Geometry only; the anchor keeps its role and
   * interactions.
   */
  anchor?: BaseCombobox.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseCombobox.Positioner.Props["disableAnchorTracking"];
  /**
   * How the popup takes its width. `anchor` matches the anchor's width, grows only with its content
   * up to the room beside it. `auto` is the content's width instead — never narrower than 204px,
   * never wider than 400px or the room beside the anchor, and held while open so a filtering list
   * does not reflow. `anchor-fixed` keeps an exact anchor width for windowed lists and caps height
   * at 288px so a mid-open available-height settle cannot shrink under the virtualizer.
   * `auto-fixed` is `auto`'s width with the same 288px cap, for a windowed list under a compact
   * trigger.
   */
  sizing?: ComboboxContentSizing;
  /** Ref to the scrolling viewport, for virtualized lists or scroll restoration. */
  viewportRef?: React.Ref<HTMLDivElement>;
  /**
   * Sticky chrome pinned above the list, e.g. a `ComboboxSearch`. When the input lives in this
   * slot, the overlay is a `role="dialog"` and needs a name — pass `aria-labelledby` pointing at
   * the visible field label, or `aria-label`.
   */
  search?: React.ReactNode;
  /** Sticky chrome pinned below the list. */
  footer?: React.ReactNode;
};

export function ComboboxContentSurface({
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
  viewportRef,
  search,
  footer,
  children,
  ...props
}: ComboboxSurfaceProps & {
  side: BaseCombobox.Positioner.Props["side"];
  sideOffset: BaseCombobox.Positioner.Props["sideOffset"];
  align: BaseCombobox.Positioner.Props["align"];
  sizing: ComboboxContentSizing;
}) {
  return (
    <BaseCombobox.Portal render={<Portal />}>
      <BaseCombobox.Positioner
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
        <BaseCombobox.Popup
          {...props}
          render={
            <OverlayPanel
              elevation="overlay"
              radius="lg"
              sizing={sizing}
              viewportRef={viewportRef}
              header={search}
              footer={footer}
            />
          }
        >
          <ComboboxPopup elevation="flat">{children}</ComboboxPopup>
        </BaseCombobox.Popup>
      </BaseCombobox.Positioner>
    </BaseCombobox.Portal>
  );
}
