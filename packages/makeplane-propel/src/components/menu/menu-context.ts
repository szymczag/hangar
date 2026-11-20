import * as React from "react";

/**
 * The trigger element, recorded by `MenuTrigger` for `MenuContent`'s `heightBehavior="fit"` — which
 * must measure the trigger against the collision boundary _before_ the positioner runs, something
 * Base UI's own (private) root context cannot be asked for. `Menu` provides it; the ref object is
 * stable, so recording the element never re-renders the tree.
 *
 * Private by convention (`<name>-context.ts` is a blessed non-export, rule 7): a consumer who needs
 * the trigger element already owns it.
 */
export const MenuTriggerElementContext =
  React.createContext<React.RefObject<HTMLElement | null> | null>(null);

/**
 * Whether the menu is open. Mirrored by `Menu` from Base UI's open state so surfaces that stay
 * mounted across open/close (and chrome that unmounts with the portal) can react to a real close
 * without treating React effect cleanup as the signal.
 */
export const MenuOpenContext = React.createContext(false);

/**
 * Slot for `MenuSearch` to register its clear-on-close callback. Owned by `MenuContentSurface`,
 * which invokes it when `MenuOpenContext` goes from open → closed — surviving portal unmount and
 * Strict Mode remounts that would falsely fire an effect cleanup.
 */
export const MenuSearchResetContext = React.createContext<React.MutableRefObject<
  (() => void) | null
> | null>(null);
