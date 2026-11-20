import * as React from "react";

import { type IconPillSize, type PillGroupSize, type PillSize } from "../../elements/pill";

/**
 * Set by the components `PillGroup` so every `Pill`/`IconPill` inside it shares one `size`. Lives
 * in the components tier: a context is cross-tree coordination — composition — not a single-element
 * `elements` concern (rule 7). `undefined` means "no enclosing group".
 */
export const PillGroupContext = React.createContext<PillGroupSize | undefined>(undefined);

/** The rung an enclosing `PillGroup` supplies, or `undefined` outside one. */
function useGroupSize(): PillGroupSize | undefined {
  return React.useContext(PillGroupContext);
}

/**
 * The effective `Pill` rung: an explicit `size` wins, otherwise the enclosing `PillGroup` supplies
 * it. Throws when neither does. There is deliberately no fallback rung — `docs/integration.md` §1
 * holds every axis required until call sites tell us the common case, the `elements` cvas carry no
 * `defaultVariants`, and a silently unsized chip is what let `ComboboxChips` and its chips drift
 * apart. `useComboboxChipSize` resolves the same way.
 */
export function usePillSize(size: PillSize | undefined): PillSize {
  // Call the hook before the `??` — inlining it would skip the read whenever `size` is passed,
  // violating the Rules of Hooks.
  const groupSize = useGroupSize();
  const resolved = size ?? groupSize;
  if (resolved == null) throw new Error("Pill requires a size or a parent PillGroup.");
  return resolved;
}

/** The effective `IconPill` rung. Resolves exactly like {@link usePillSize}. */
export function useIconPillSize(size: IconPillSize | undefined): IconPillSize {
  const groupSize = useGroupSize();
  const resolved = size ?? groupSize;
  if (resolved == null) throw new Error("IconPill requires a size or a parent PillGroup.");
  return resolved;
}
