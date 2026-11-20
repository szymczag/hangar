import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { ScrollportXClip } from "../../internal/scrollport-x-clip";
import { alertDialogBodyClipVariants, alertDialogBodyVariants } from "./variants";

export type AlertDialogBodyProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The padded content region of the alert dialog popup (20px top and sides, 12px bottom). Stacks the
 * header (icon + intro) and any optional body content (form fields, extra copy) with a 16px gap.
 * Caps height so tall content scrolls while the actions footer stays pinned. Wide descendants are
 * constrained by an inner `overflow-x-clip` wrapper so focus scrolling cannot pan sideways.
 *
 * Not focusable by default, so the dialog's initial focus lands on the first action button rather
 * than on a region nothing can be done with (Dialog pattern). When the body can overflow, pass
 * `tabIndex={0}` so the scroll region is keyboard-reachable (WCAG 2.1.1); pair it with
 * `initialFocus` on `AlertDialogContent` if focus should still start on an action.
 */
export function AlertDialogBody({ render, children, ...props }: AlertDialogBodyProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: alertDialogBodyVariants() }, props, {
      children: (
        <ScrollportXClip className={alertDialogBodyClipVariants()}>{children}</ScrollportXClip>
      ),
    }),
  });
}
