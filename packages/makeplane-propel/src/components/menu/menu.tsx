import { Menu as BaseMenu } from "@base-ui/react/menu";
import type { MenuRoot } from "@base-ui/react/menu";
import * as React from "react";

import { PayloadChildren } from "../../internal/payload-children";
import { MenuOpenContext, MenuTriggerElementContext } from "./menu-context";

export type MenuProps<Payload = unknown> = Omit<
  MenuRoot.Props<Payload>,
  "open" | "defaultOpen" | "onOpenChange" | "modal" | "children"
> & {
  /** Whether the menu is open. Controlled; pair with `onOpenChange`. */
  open?: boolean;
  /** Whether the menu is open on mount. Uncontrolled. @default false */
  defaultOpen?: boolean;
  /** Called with the next open state when the menu opens or closes. */
  onOpenChange?: MenuRoot.Props<Payload>["onOpenChange"];
  /**
   * Whether the menu enters a modal state when open, like `Select`: page scroll is locked and a
   * press outside the menu only dismisses it. The trigger is cut out of the backdrop. Set `false`
   * to leave the rest of the page interactive while the menu is open. Submenus ignore this prop,
   * and a menu opened by hover is never modal.
   *
   * @default true
   */
  modal?: MenuRoot.Props<Payload>["modal"];
  /** The trigger and menu surface (`MenuTrigger`, `MenuContent`). */
  children?: MenuRoot.Props<Payload>["children"];
};

/**
 * The menu Root — Base UI's context/state provider (renders no element of its own). A behavior-only
 * role, so it lives in `components` (rules 1a, 2); the styled parts live in `elements/menu` and are
 * grafted onto Base UI behavior here.
 */
export function Menu<Payload = unknown>({
  open,
  defaultOpen,
  onOpenChange,
  children,
  ...props
}: MenuProps<Payload>) {
  // A stable home for the trigger element, recorded by `MenuTrigger` and read by
  // `MenuContent`'s `heightBehavior="fit"` — see menu-context.ts.
  const triggerElement = React.useRef<HTMLElement | null>(null);
  // Mirror open so portal chrome (e.g. `MenuSearch`) can reset on a real close, not on effect
  // cleanup — Strict Mode remounts would otherwise clear a live query.
  const [isOpen, setIsOpen] = React.useState(() => open ?? defaultOpen ?? false);
  React.useEffect(() => {
    if (open !== undefined) setIsOpen(open);
  }, [open]);
  const handleOpenChange = React.useCallback<NonNullable<MenuProps<Payload>["onOpenChange"]>>(
    (nextOpen, eventDetails) => {
      setIsOpen(nextOpen);
      onOpenChange?.(nextOpen, eventDetails);
    },
    [onOpenChange],
  );

  return (
    <MenuTriggerElementContext.Provider value={triggerElement}>
      <MenuOpenContext.Provider value={isOpen}>
        <BaseMenu.Root
          {...props}
          children={
            typeof children === "function"
              ? ({ payload }) => <PayloadChildren render={children} payload={payload} />
              : children
          }
          open={open}
          defaultOpen={defaultOpen}
          onOpenChange={handleOpenChange}
        />
      </MenuOpenContext.Provider>
    </MenuTriggerElementContext.Provider>
  );
}
