import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva } from "class-variance-authority";

/**
 * The shared overlay backdrop surface, grafted onto any Base UI `*.Backdrop` behavior in
 * `components` (`<BaseDialog.Backdrop render={<Backdrop />}>`). Dims the page behind a MODAL
 * overlay and fades with the overlay's open/close transition. Shared by Dialog and Drawer; Alert
 * Dialog owns its distinct 25% scrim. No styling axes.
 *
 * Reach for this only when the overlay is genuinely modal (traps focus, blocks the rest of the
 * page). A non-modal, hover/focus-triggered surface — preview-card, popover, tooltip, menu,
 * context-menu — has no business dimming the page just because it's open; it doesn't graft a
 * `*.Backdrop` behavior at all, styled or not.
 *
 * `z-50` matches the dialog / alert-dialog viewports and the drawer's own overlay, so the backdrop
 * shares a layer with the popup it dims — the popup still paints on top because the portal renders
 * the backdrop first. Without it the backdrop is `z-index: auto`, which loses to any positioned
 * host chrome with a positive z-index no matter how late it appears in the DOM: in Plane the app
 * rail (z-26), sidebar (z-20) and header (z-18) all stayed undimmed behind an open dialog.
 */
export const backdropVariants = cva(
  "fixed inset-0 z-50 bg-backdrop transition-opacity duration-200 data-closed:pointer-events-none data-ending-style:pointer-events-none data-ending-style:opacity-0 data-starting-style:opacity-0 motion-reduce:transition-none",
);

export type BackdropProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

export function Backdrop({ render, ...props }: BackdropProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: backdropVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
