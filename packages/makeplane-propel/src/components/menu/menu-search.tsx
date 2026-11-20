import * as React from "react";

import { MenuSearch as MenuSearchElement, MenuSearchInput } from "../../elements/menu";
import { SearchOutline } from "../../icons";
import { Icon } from "../../internal/icon";
import { MenuSearchResetContext } from "./menu-context";

const MENU_ITEM_SELECTOR =
  '[role="menuitem"]:not([data-disabled]):not([aria-disabled="true"]), [role="menuitemcheckbox"]:not([data-disabled]):not([aria-disabled="true"]), [role="menuitemradio"]:not([data-disabled]):not([aria-disabled="true"])';

/** The `role="menu"` popup this field filters: the nearest ancestor that contains one. */
function menuPopupFrom(input: HTMLElement): HTMLElement | null {
  for (let node = input.parentElement; node; node = node.parentElement) {
    const menu = node.querySelector<HTMLElement>('[role="menu"]');
    if (menu) return menu;
  }
  return null;
}

export type MenuSearchProps = Omit<
  React.ComponentPropsWithoutRef<"input">,
  "className" | "style" | "onChange" | "value" | "defaultValue" | "type"
> & {
  /** Current search text. Omit it to let the field manage its own state (see `defaultValue`). */
  value?: string;
  /** Initial search text when the field manages its own state. @default "" */
  defaultValue?: string;
  /**
   * Called with the new text on each keystroke — and with `""` when the menu closes (see
   * `resetOnClose`).
   */
  onValueChange?: (value: string) => void;
  /**
   * Clear the query when the menu closes. The field's own state resets with the popup unmount; this
   * also calls `onValueChange("")` on close so a consumer-held query — which outlives the popup —
   * is cleared too and the list is unfiltered on reopen. Turn it off to keep a _controlled_ query
   * across opens on purpose; an uncontrolled field (`defaultValue`) resets with the popup either
   * way, so all the flag changes there is whether `onValueChange("")` fires.
   *
   * @default true
   */
  resetOnClose?: boolean;
  /** Placeholder text. */
  placeholder?: string;
};

/**
 * A sticky search field pinned above a `MenuContent` popup, via its `search` prop. The menu focuses
 * it on open (it sits outside the `role="menu"` popup — a menu may not own a textbox — so the
 * hand-off is programmatic, not Tab). Text-editing keys stay in the field, which keeps the menu's
 * type-ahead from stealing them; Escape closes the menu, and ArrowDown/ArrowUp move focus into the
 * list — first row down, last row up.
 */
export function MenuSearch({
  value,
  defaultValue = "",
  onValueChange,
  resetOnClose = true,
  placeholder,
  onKeyDown,
  ...props
}: MenuSearchProps) {
  const [internal, setInternal] = React.useState(defaultValue);
  const controlled = value !== undefined;

  // Register the clear with `MenuContentSurface`, which fires it when the menu actually closes.
  // Do not clear from this component's effect cleanup — Strict Mode remounts and `resetOnClose`
  // toggles would call `onValueChange("")` while the menu is still open.
  const searchResetRef = React.useContext(MenuSearchResetContext);
  const onValueChangeRef = React.useRef(onValueChange);
  onValueChangeRef.current = onValueChange;
  React.useLayoutEffect(() => {
    if (!searchResetRef) return;
    searchResetRef.current = resetOnClose ? () => onValueChangeRef.current?.("") : null;
  }, [resetOnClose, searchResetRef]);

  return (
    <MenuSearchElement>
      <Icon tint="tertiary" size="md">
        <SearchOutline />
      </Icon>
      <MenuSearchInput
        type="text"
        value={controlled ? value : internal}
        onChange={(event) => {
          if (!controlled) setInternal(event.target.value);
          onValueChange?.(event.target.value);
        }}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (event.defaultPrevented) return;
          // The field lives outside the popup, so the menu never sees its keys; the seam routes
          // the three the menu owns and keeps the rest (text editing) from the menu's type-ahead.
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            event.stopPropagation();
            const items = menuPopupFrom(event.currentTarget)?.querySelectorAll<HTMLElement>(
              MENU_ITEM_SELECTOR,
            );
            if (items?.length) items[event.key === "ArrowDown" ? 0 : items.length - 1].focus();
            return;
          }
          // Escape must reach Base UI's dismiss listener; Tab keeps its native fate.
          if (event.key !== "Escape" && event.key !== "Tab") event.stopPropagation();
        }}
        placeholder={placeholder}
        {...props}
      />
    </MenuSearchElement>
  );
}
