import { Popover as BasePopover } from "@base-ui/react/popover";
import type { PopoverRoot } from "@base-ui/react/popover";

import { PayloadChildren } from "../../internal/payload-children";
import { isClickDisabledTrigger } from "./popover-context";

export type PopoverProps<Payload = unknown> = Omit<
  PopoverRoot.Props<Payload>,
  "open" | "defaultOpen" | "onOpenChange" | "modal" | "children"
> & {
  /** Whether the popover is open. Controlled; pair with `onOpenChange`. */
  open?: boolean;
  /** Whether the popover is open on mount. Uncontrolled. @default false */
  defaultOpen?: boolean;
  /** Called with the next open state when the popover opens or closes. */
  onOpenChange?: PopoverRoot.Props<Payload>["onOpenChange"];
  /**
   * How the rest of the page behaves while open. Off by default so the page stays interactive.
   * `true` locks page scroll and outside pointers; `"trap-focus"` keeps focus in the panel without
   * locking the page. Focus trapping in either mode needs `PopoverClose` inside the popup so touch
   * screen readers can leave. There is no backdrop — the panel does not dim the page.
   *
   * @default false
   */
  modal?: PopoverRoot.Props<Payload>["modal"];
  /**
   * The popover's trigger and panel (`PopoverTrigger`, `PopoverContent`) and any title,
   * description, or close parts composed inside.
   */
  children?: PopoverRoot.Props<Payload>["children"];
};

export function Popover<Payload = unknown>({
  onOpenChange,
  children,
  ...props
}: PopoverProps<Payload>) {
  return (
    <BasePopover.Root
      {...props}
      children={
        typeof children === "function"
          ? ({ payload }) => <PayloadChildren render={children} payload={payload} />
          : children
      }
      onOpenChange={(open, details) => {
        // Hover-only triggers mark themselves so a mouse click does not toggle. Keyboard and
        // touch still use `trigger-press` so the panel is not pointer-locked.
        if (
          details.reason === "trigger-press" &&
          isClickDisabledTrigger(details.trigger) &&
          isMouseTriggerPress(details.event)
        ) {
          details.cancel();
          return;
        }
        onOpenChange?.(open, details);
      }}
    />
  );
}

function isMouseTriggerPress(event: Event) {
  if (event instanceof KeyboardEvent) return false;
  if (typeof PointerEvent !== "undefined" && event instanceof PointerEvent) {
    return event.pointerType === "mouse" || event.pointerType === "pen";
  }
  if (typeof TouchEvent !== "undefined" && event instanceof TouchEvent) return false;
  return event instanceof MouseEvent && event.detail > 0;
}
