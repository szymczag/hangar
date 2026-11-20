import { Popover as BasePopover } from "@base-ui/react/popover";
import * as React from "react";

import { setTriggerClickPolicy } from "./popover-context";

export type PopoverTriggerProps<Payload = unknown> = Omit<
  BasePopover.Trigger.Props<Payload>,
  "className" | "style" | "openOnHover" | "delay" | "closeDelay" | "ref"
> & {
  /**
   * Open the panel when the pointer hovers the trigger. Pair with `openOnClick={false}` for
   * hover-only (a mouse click no longer toggles; keyboard and touch still open).
   *
   * @default false
   */
  openOnHover?: boolean;
  /**
   * Open or close the panel when the trigger is clicked with a mouse. Set `false` with
   * `openOnHover` when the panel should open on hover only.
   *
   * @default true
   */
  openOnClick?: boolean;
  /**
   * How long to wait, in milliseconds, before opening on hover. Requires `openOnHover`.
   *
   * @default 300
   */
  delay?: number;
  /**
   * How long to wait, in milliseconds, before closing a hover-opened panel. Requires `openOnHover`.
   *
   * @default 0
   */
  closeDelay?: number;
};

/**
 * The element that opens the popover. Renders a `<button>` by default; pass `render` to project the
 * trigger onto any control (`Button`, `IconButton`, a custom element). The panel anchors to
 * whichever trigger opened it.
 *
 * Interaction: click only (default), click + hover (`openOnHover`), or hover only (`openOnHover`
 * and `openOnClick={false}`).
 */
export function PopoverTrigger<Payload = unknown>({
  openOnClick = true,
  ref,
  ...props
}: PopoverTriggerProps<Payload> & { ref?: React.Ref<HTMLElement> }) {
  const record = React.useCallback(
    (node: HTMLButtonElement | null) => {
      setTriggerClickPolicy(node, openOnClick);
      if (typeof ref === "function") return ref(node);
      if (ref) ref.current = node;
    },
    [openOnClick, ref],
  );
  return <BasePopover.Trigger {...props} ref={record} />;
}
