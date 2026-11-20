import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva } from "class-variance-authority";

/**
 * The shared overlay portal root, grafted onto the Base UI `*.Portal` of every anchored overlay
 * whose `modal` mode renders Base UI's internal backdrop — Menu (and so ContextMenu), Popover,
 * Select and Combobox (`<BaseMenu.Portal render={<Portal />}>`).
 *
 * That internal backdrop is what makes `modal` modal: a transparent `fixed inset-0` sibling Base UI
 * renders just before the positioner, inside this portal, carrying `data-base-ui-inert`. It ships
 * with no z-index and no styling hook, so — like the shared `Backdrop` before it took `z-50` — it
 * sits at `z-index: auto` and loses to any positioned host chrome with a positive z-index. In
 * Plane, sticky headers, the sidebar and `z-10`/`z-20` list rows kept taking hovers, clicks and
 * wheel scrolls while a "modal" menu was open.
 *
 * `z-50` on that child matches the shared `Backdrop` and `Positioner`, so the backdrop shares the
 * popup's layer and the popup still paints on top (the backdrop comes first in the DOM). The portal
 * itself stays unpositioned — no stacking context, no new offsetParent — so absolute positioning
 * and a nested submenu's own portal are unaffected. Base UI still decides WHEN the backdrop exists
 * (modal only, not hover-opened, not nested) and cuts the trigger or input out of it; this only
 * lifts it. Dialog, AlertDialog and Drawer graft the shared `Backdrop` instead and need none of
 * this.
 */
export const portalVariants = cva("[&>[data-base-ui-inert]]:z-50");

export type PortalProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

export function Portal({ render, ...props }: PortalProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: portalVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
