import { Menu as BaseMenu } from "@base-ui/react/menu";
import * as React from "react";

import { MenuTriggerElementContext } from "./menu-context";

export type MenuTriggerProps<Payload = unknown> = Omit<
  BaseMenu.Trigger.Props<Payload>,
  "className" | "style" | "ref"
>;

/**
 * The button that opens the menu — Base UI's `Menu.Trigger` passthrough. Propel ships no menu
 * trigger chrome (any control can open a menu), so graft the behavior onto the control you already
 * have via `render` (`<MenuTrigger render={<Button …/>}>`); Base UI contributes the open/close
 * behavior, ARIA wiring, and `data-*` state.
 *
 * The trigger also records its element for `MenuContent`'s default `heightBehavior="fit"` to
 * measure against. A consumer `ref` is chained after that recording rather than spread over it: in
 * the forward graft (`<Button render={<MenuTrigger />} />`, `<Pill render={<MenuTrigger />} />`)
 * Base UI clones this element with the button's own `ref` in its props, and a `{...props}` after
 * `ref={record}` would replace the recorder — nothing recorded, `fit` silently falling back to
 * `flip`. Same shape as `PopoverTrigger`.
 */
export function MenuTrigger<Payload = unknown>({
  ref,
  ...props
}: MenuTriggerProps<Payload> & { ref?: React.Ref<HTMLElement> }) {
  const triggerElement = React.useContext(MenuTriggerElementContext);
  const record = React.useCallback(
    (element: HTMLElement | null) => {
      if (triggerElement) triggerElement.current = element;
      if (typeof ref === "function") {
        const cleanup = ref(element);
        if (cleanup) {
          return () => {
            if (triggerElement) triggerElement.current = null;
            cleanup();
          };
        }
      } else if (ref) ref.current = element;
    },
    [triggerElement, ref],
  );
  return <BaseMenu.Trigger {...props} ref={record} />;
}
