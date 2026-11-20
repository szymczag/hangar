import { Autocomplete as BaseAutocomplete } from "@base-ui/react/autocomplete";

import { DROPDOWN_EDGE_GAP_PX } from "../../internal/dropdown-edge-gap";
import { ListboxPopup, type ListboxPopupProps } from "../../internal/listbox-popup";
import { Positioner } from "../../internal/positioner";

export type AutocompleteContentProps = ListboxPopupProps & {
  /** Which side of the input the list opens toward. @default "bottom" */
  side?: BaseAutocomplete.Positioner.Props["side"];
  /** Distance in px between the input and the list. @default 4 */
  sideOffset?: BaseAutocomplete.Positioner.Props["sideOffset"];
  /** Alignment of the list relative to the input along `side`. @default "start" */
  align?: BaseAutocomplete.Positioner.Props["align"];
  /**
   * Additional offset in px along the align axis — slides the list along the input's edge without
   * changing `align`.
   *
   * @default 0
   */
  alignOffset?: BaseAutocomplete.Positioner.Props["alignOffset"];
  /**
   * Minimum gap in px between the list and the viewport edge it would otherwise touch.
   *
   * @default 16
   */
  collisionPadding?: BaseAutocomplete.Positioner.Props["collisionPadding"];
  /**
   * The element or rect the list is confined to when avoiding collisions. Base UI's clipping
   * ancestors when unset.
   */
  collisionBoundary?: BaseAutocomplete.Positioner.Props["collisionBoundary"];
  /**
   * What to do when the list would overflow the boundary, set per axis: flip to the other side,
   * shift along it, or stay put. Base UI flips the side and shifts the alignment when unset.
   */
  collisionAvoidance?: BaseAutocomplete.Positioner.Props["collisionAvoidance"];
  /**
   * Keep the list on screen after the input scrolls out of view, instead of following it out.
   *
   * @default false
   */
  sticky?: BaseAutocomplete.Positioner.Props["sticky"];
  /**
   * Which CSS `position` the positioner uses. `fixed` escapes overflow-clipping ancestors, e.g. an
   * input inside a sticky header.
   *
   * @default "absolute"
   */
  positionMethod?: BaseAutocomplete.Positioner.Props["positionMethod"];
  /**
   * Position against this element instead of the input — an element, a ref, a virtual element, or a
   * function returning one. Geometry only; the input keeps its role and interactions.
   */
  anchor?: BaseAutocomplete.Positioner.Props["anchor"];
  /**
   * Stop tracking layout shifts of the anchor — position once, on open.
   *
   * @default false
   */
  disableAnchorTracking?: BaseAutocomplete.Positioner.Props["disableAnchorTracking"];
};

/** The autocomplete list surface: Base UI portal + positioner + popup grafted onto Propel styling. */
export function AutocompleteContent({
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
  ...props
}: AutocompleteContentProps) {
  return (
    <BaseAutocomplete.Portal>
      <BaseAutocomplete.Positioner
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
        <BaseAutocomplete.Popup {...props} render={<ListboxPopup />} />
      </BaseAutocomplete.Positioner>
    </BaseAutocomplete.Portal>
  );
}
