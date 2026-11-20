import * as React from "react";

export type SuggestionMenuContextValue = {
  /** Current highlight, also read synchronously by the imperative keyboard handler. */
  getSnapshot: () => string | null;
  subscribe: (listener: () => void) => () => void;
  /** Moves the highlight to the row with this `id`. */
  highlight: (id: string | null) => void;
};

/** One selection source per menu. Rows subscribe to their boolean state, not the changing ID. */
export function createSuggestionMenuStore(): SuggestionMenuContextValue {
  let highlightedId: string | null = null;
  const listeners = new Set<() => void>();
  return {
    getSnapshot: () => highlightedId,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    highlight: (id) => {
      if (id === highlightedId) return;
      highlightedId = id;
      listeners.forEach((listener) => listener());
    },
  };
}

export const SuggestionMenuContext = React.createContext<SuggestionMenuContextValue | null>(null);

export function useSuggestionMenuContext(): SuggestionMenuContextValue {
  const context = React.useContext(SuggestionMenuContext);
  if (!context) {
    throw new Error("SuggestionMenuItem must be rendered inside a SuggestionMenu.");
  }
  return context;
}
