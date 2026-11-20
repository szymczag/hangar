import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { ScrollportXClip } from "../../internal/scrollport-x-clip";
import { dialogBodyVariants } from "./variants";

export type DialogBodyProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The scrollable main slot inside `DialogMain`. Grows to fill available space and scrolls
 * vertically when content exceeds the popup's max-height. `overflow-x-clip` on this node keeps
 * trackpad deltas from panning sideways; an inner width clipper keeps focus scrolling from shifting
 * the body under sticky header/footer. A 2 px padded bleed keeps field `ring-2` focus chrome from
 * being masked by the vertical clip. Pass form fields, lists, or other slot content — keep
 * `DialogDescription` in `DialogHeading`.
 *
 * When the body can overflow, pass `tabIndex={0}` so the scroll region is keyboard-reachable (axe
 * `scrollable-region-focusable`).
 */
export function DialogBody({ render, children, ...props }: DialogBodyProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: dialogBodyVariants() }, props, {
      children: <ScrollportXClip>{children}</ScrollportXClip>,
    }),
  });
}
