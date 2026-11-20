import { createContext, useContext } from "react";

/**
 * How a single-select menu group marks its current row. Read by `MenuRadioItem` and
 * `ContextMenuRadioItem`, provided by their groups. React context is a composition concern — never
 * `elements` (rule 7) — and this one is shared by two `components` families, so it lives here in
 * `internal` (rule 4a) rather than having `context-menu` import it from `menu`.
 *
 * `check` (default) — the trailing tick every other single-select row in the library uses. `radio`
 * — the leading 16px ring, drawn on every row. Reserved for the one case that needs it: a popup
 * that mixes a multi-select group with a single-select one, where a shared marker would make the
 * two read as the same kind of choice. With nothing to disambiguate from, the ring adds a second
 * control language and a second round shape to rows that often already lead with one.
 */
export type MenuRadioMarker = "check" | "radio";

export const MenuRadioMarkerContext = createContext<MenuRadioMarker>("check");

export const useMenuRadioMarker = (): MenuRadioMarker => useContext(MenuRadioMarkerContext);
