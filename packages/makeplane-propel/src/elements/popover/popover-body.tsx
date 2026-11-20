import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { ScrollportXClip } from "../../internal/scrollport-x-clip";
import { popoverBodyVariants } from "./variants";

export type PopoverBodyProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The scrollable slot inside `PopoverContent`. Grows to fill leftover space under the popup's
 * available-height cap and scrolls when the body is taller than that space. Wide descendants are
 * constrained by an inner `overflow-x-clip` wrapper so focus scrolling cannot pan sideways. Put
 * forms and long stacks here; keep `PopoverTitle` and action rows as siblings so they stay pinned.
 *
 * When the body can overflow, pass `tabIndex={0}` so the scroll region is keyboard-reachable (axe
 * `scrollable-region-focusable`).
 */
export function PopoverBody({ render, children, ...props }: PopoverBodyProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: popoverBodyVariants() }, props, {
      children: <ScrollportXClip>{children}</ScrollportXClip>,
    }),
  });
}
