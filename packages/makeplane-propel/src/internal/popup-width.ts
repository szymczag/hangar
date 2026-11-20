import { cx } from "class-variance-authority";
import * as React from "react";

/**
 * The popup width rule: one floor and one ceiling for every overlay panel — the
 * `internal/overlay-panel` shell behind menus, context menus, submenus and the combobox list, and
 * the standalone raised menu popup.
 *
 * A panel is as wide as its content, never narrower than the floor and never wider than the ceiling
 * — or the room Base UI measured beside the anchor (`--available-width`). Nothing here is a fixed
 * width, because a fixed width fails in both directions at once: it is too wide for a five-word
 * menu and too narrow for the same menu the moment a row grows a description.
 *
 * There is no ladder of named widths between the two. The product code these panels replace carried
 * thirty-odd fixed widths (`w-48`, `w-64`, `w-72`, `w-[258px]`, …) that tracked which legacy
 * primitive a screen was built with rather than any design intent, and the systems propel is
 * measured against (Base UI, Radix, Material, Fluent, Spectrum, Primer) all size an action menu by
 * its content between a small floor and a ceiling. The floor keeps a one-word menu reading as part
 * of the family and leaves a search field room; the ceiling keeps a long row truncating instead of
 * running across the page. A panel that needs to be wider than its rows is not a wider rung — it is
 * `sizing="anchor"`, which takes the trigger's width instead.
 *
 * Invariants (each enforced by `popup-width.test.ts`): the floor is below the ceiling; both sit on
 * the 4px grid; `styles/variables.css` carries exactly these values; and the panel cvas read the
 * tokens rather than restating the numbers.
 */
export const POPUP_WIDTH = {
  /** The floor, in px. Where content width starts: a short menu is this wide. */
  min: 204,
  /** The ceiling, in px. Content past it truncates. */
  max: 400,
} as const;

// The width rule (tokens in `styles/variables.css`): the panel is as
// wide as its content, never narrower than the floor and never wider than the ceiling — and both
// yield to the room Base UI measured beside the anchor (`--available-width`). The floor must yield
// too: CSS resolves `min-width` over `max-width`, so a floor that did not would push a panel off a
// narrow screen. `100vw` stands in for the room on a panel rendered outside a positioner.
//
// `--popup-held-width` is the width the panel has already reached while open (see
// `useHeldWidth`). It raises the floor to that width so a list that filters down to its shortest
// rows keeps the width it opened at, instead of reflowing under the pointer with every keystroke.
export const popupWidthRule = cx(
  "min-w-[min(max(var(--popup-width-min),var(--popup-held-width,0px)),var(--available-width,100vw))]",
  "max-w-[min(var(--popup-width-max),var(--available-width,100vw))]",
);

/**
 * Hold an open panel's width: a panel that sizes to its content may grow while it is open (rows
 * arriving, a description appearing) but never shrinks until it closes. A searchable list would
 * otherwise reflow under the pointer as typing filters it down to its shortest rows — the one
 * reason the product code these panels replace pinned a fixed width on every picker. Filterable
 * lists in Base UI, Primer and Ant Design freeze their width the same way (to the anchor or a
 * preset); here the frozen width is the content's own.
 *
 * The widest width seen goes onto the element as `--popup-held-width`, which the width rule reads
 * as part of the floor, so it still yields to the ceiling and to `--available-width`. Keyed by
 * element: the popup mounts fresh each open, so the hold resets with it.
 */
export function useHeldWidth(enabled: boolean): React.RefCallback<HTMLDivElement> | undefined {
  const [element, setElement] = React.useState<HTMLDivElement | null>(null);
  React.useLayoutEffect(() => {
    if (!enabled || element == null) return undefined;
    let held = 0;
    const hold = () => {
      // Layout width: the open transition scales the panel with `transform`, which `offsetWidth`
      // does not include.
      const width = element.offsetWidth;
      if (width > held) {
        held = width;
        element.style.setProperty("--popup-held-width", `${width}px`);
      }
    };
    hold();
    const observer = new ResizeObserver(hold);
    observer.observe(element);
    return () => {
      observer.disconnect();
      element.style.removeProperty("--popup-held-width");
    };
  }, [enabled, element]);
  return enabled ? setElement : undefined;
}
