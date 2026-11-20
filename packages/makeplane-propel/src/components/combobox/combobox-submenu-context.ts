import * as React from "react";

export type ComboboxSubmenuContextValue = {
  /** Whether the nested list is open. */
  open: boolean;
  /** Opens or closes the nested list immediately, cancelling any pending hover timer. */
  setOpen: (open: boolean) => void;
  /** The parent row that the nested list anchors to and highlights against. */
  triggerRef: React.RefObject<HTMLDivElement | null>;
  /** Arms the hover-open timer (no-op when `openOnHover` is off, or when already open). */
  scheduleOpen: () => void;
  /** Arms the hover-close timer. The nested list cancels it while the pointer is inside it. */
  scheduleClose: () => void;
  /** Cancels whichever hover timer is pending — used when the pointer re-enters either surface. */
  cancelScheduled: () => void;
  /** Whether `Escape` inside the nested list should also close the parent combobox. */
  closeParentOnEsc: boolean;
};

/**
 * Shared state for one `ComboboxSubmenu`: the open flag, the parent row it anchors to, and the
 * hover timers the trigger and the nested surface hand back and forth. Private to the family (rule
 * 7) — the index deliberately does not export it.
 */
export const ComboboxSubmenuContext = React.createContext<ComboboxSubmenuContextValue | null>(null);

export function useComboboxSubmenuContext(part: string): ComboboxSubmenuContextValue {
  const context = React.useContext(ComboboxSubmenuContext);
  if (context === null) {
    throw new Error(`\`${part}\` must be rendered inside a \`ComboboxSubmenu\`.`);
  }
  return context;
}
