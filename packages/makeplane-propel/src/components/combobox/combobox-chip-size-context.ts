import * as React from "react";

import { type ComboboxChipSize } from "../../elements/combobox";

/**
 * Set by the components `ComboboxChips` so every chip inside the frame shares its `size`.
 *
 * Chips are consumer-rendered — `ComboboxChips` takes a `children` render function and Base UI
 * derives which selected value each chip represents from its position among its siblings — so the
 * frame cannot pass `size` down as a prop. A context is the only way the chip can inherit it
 * without every call site repeating the frame's own size, and context is a composition concern, so
 * it lives here rather than in `elements` (rule 7).
 */
export const ComboboxChipSizeContext = React.createContext<ComboboxChipSize | undefined>(undefined);

/**
 * The effective chip size: an explicit `size` wins, otherwise the enclosing `ComboboxChips`
 * supplies it. Throws when neither is present — a chip has no sensible default size, and silently
 * rendering an unsized chip is what let the frame and its chips drift apart in the first place.
 */
export function useComboboxChipSize(size?: ComboboxChipSize): ComboboxChipSize {
  // Read the context unconditionally — `size ?? React.useContext(…)` would skip the hook call
  // whenever `size` is passed, violating the Rules of Hooks.
  const inheritedSize = React.useContext(ComboboxChipSizeContext);
  const resolvedSize = size ?? inheritedSize;

  if (resolvedSize == null) {
    throw new Error("ComboboxChip requires a size or a parent ComboboxChips.");
  }

  return resolvedSize;
}
