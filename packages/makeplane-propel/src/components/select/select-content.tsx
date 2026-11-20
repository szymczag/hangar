import { Select as BaseSelect } from "@base-ui/react/select";
import type * as React from "react";

import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { OverlayPanel, type OverlayPanelSizingCurrent } from "../../internal/overlay-panel";
import { Portal } from "../../internal/portal";
import { Positioner } from "../../internal/positioner";

// `auto-fixed` exists for windowed combobox lists; a Select is never windowed.
export type SelectContentSizing = Exclude<OverlayPanelSizingCurrent, "auto-fixed">;

export type SelectContentProps = Omit<BaseSelect.Popup.Props, "className" | "render" | "style"> & {
  /**
   * How the popup takes its width. `anchor` matches the trigger's width, growing only with its
   * content up to the room beside the trigger. `auto` is the content's width instead — never
   * narrower than 204px, never wider than 400px or the room beside the trigger — for a narrow
   * trigger (e.g. a ghost select in a toolbar) whose options need more room than it has.
   *
   * @default "anchor"
   */
  sizing?: SelectContentSizing;
  /**
   * Sticky content pinned above the scrolling list, e.g. a `SelectStickyList` holding a
   * `SelectSelectAll` row and a `SelectSeparator`.
   */
  header?: React.ReactNode;
  /** Sticky content pinned below the scrolling list, e.g. a `SelectFooter`. */
  footer?: React.ReactNode;
  /** Which side of the trigger the list opens toward. @default "bottom" */
  side?: BaseSelect.Positioner.Props["side"];
  /** Distance in px between the trigger and the list. @default 4 */
  sideOffset?: BaseSelect.Positioner.Props["sideOffset"];
  /** Alignment of the list relative to the trigger along `side`. @default "start" */
  align?: BaseSelect.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the list along the trigger's edge without
   * changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseSelect.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the list and the viewport edge it would otherwise touch.
   *
   * @default 16
   */
  collisionPadding?: BaseSelect.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the list is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseSelect.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the list would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseSelect.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the list on screen after the trigger scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BaseSelect.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. a
   * trigger inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BaseSelect.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the trigger — an element, a ref, a virtual element, or
   * a function returning one. Geometry only; the trigger keeps its role and interactions.
   */
  anchor?: BaseSelect.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseSelect.Positioner.Props["disableAnchorTracking"];
  /**
   * Overlap the popup onto the trigger so the selected item's text lines up with the trigger's
   * value (native `<select>`-style). Figma's spec opens the list flush below the trigger instead,
   * so this defaults off — enable per-instance for the native-alignment look. While it is on, Base
   * UI scrolls the list element itself rather than the panel's `ScrollArea`, so the list shows the
   * native scrollbar instead of the panel's.
   *
   * @default false
   */
  alignItemWithTrigger?: BaseSelect.Positioner.Props["alignItemWithTrigger"];
};

/**
 * The select list surface: Base UI portal + positioner, with the popup grafted onto the shared
 * `OverlayPanel` — the same elevated card, radius, open/close animation and anchor width as the
 * Combobox and Menu panels, including the `ScrollArea` its list scrolls in.
 */
export function SelectContent({
  side = "bottom",
  sideOffset = 4,
  align = "start",
  alignOffset,
  collisionPadding = DROPDOWN_EDGE_GAP_PX,
  collisionBoundary,
  collisionAvoidance,
  sticky,
  positionMethod,
  anchor,
  disableAnchorTracking,
  alignItemWithTrigger = false,
  sizing = "anchor",
  header,
  footer,
  ...props
}: SelectContentProps) {
  return (
    <BaseSelect.Portal render={<Portal />}>
      <BaseSelect.Positioner
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
        alignItemWithTrigger={alignItemWithTrigger}
        render={<Positioner />}
      >
        <BaseSelect.Popup
          {...props}
          render={
            <OverlayPanel
              elevation="overlay"
              radius="lg"
              sizing={sizing}
              header={header}
              footer={footer}
            />
          }
        />
      </BaseSelect.Positioner>
    </BaseSelect.Portal>
  );
}
