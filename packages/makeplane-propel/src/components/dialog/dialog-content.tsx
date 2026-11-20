import { Dialog as BaseDialog } from "@base-ui/react/dialog";

import {
  DialogPopup,
  type DialogDensity,
  type DialogPopupHeight,
  type DialogPopupProps,
  type DialogPopupSize,
} from "../../elements/dialog/dialog-popup";
import { DialogViewport } from "../../elements/dialog/dialog-viewport";
import { Backdrop } from "../../internal/backdrop";
import { DialogDensityContext, DialogPanesContext, DialogSizeContext } from "./dialog-context";

export type { DialogDensity, DialogPopupHeight, DialogPopupSize };

export type DialogContentProps = Omit<DialogPopupProps, "render" | "size" | "height"> & {
  /**
   * Dialog width: `xs` 480 px, `sm` 576 px, `md` 672 px, `lg` 800 px, `xl` 1000 px, or `full`,
   * which fills the viewport minus an 80 px margin on every edge and pins the height as well. The
   * ready-made `DialogMain`, `DialogToolbar`, `DialogActions`, and `DialogAside` read it for their
   * gutter (16 px, 48 px at `full`).
   *
   * @default "md"
   */
  size?: DialogPopupSize;
  /**
   * Dialog height. `auto` (default) sizes to content up to the viewport ceiling. `fixed` pins 700
   * px so split chrome does not resize when the active pane changes. Prefer `size="full"` when the
   * popup should fill the viewport.
   *
   * @default "auto"
   */
  height?: DialogPopupHeight;
  /**
   * Compactness of Main / Toolbar / Actions / Aside gutters. `size` already picks the popup width
   * and the default gutter; `density` is the second axis when that coupling is wrong. `comfortable`
   * (the default) is 16 px, 48 px at `full`. `compact` keeps 16 px at every size, including
   * `full`.
   *
   * @default "comfortable"
   */
  density?: DialogDensity;
};

/**
 * Convenience that composes the dialog overlay boilerplate — portal, shared `Backdrop`, the
 * top-anchored `DialogViewport`, and the `DialogPopup` — so a consumer only writes the trigger and
 * the popup body. Each Base UI behavior part grafts onto its styled element via `render`.
 *
 * Nested dialogs keep their own dim: Base UI omits a nested Backdrop unless `forceRender` is set,
 * which would leave a child modal sitting on the parent with no extra overlay. Closed
 * force-rendered backdrops set `pointer-events: none` so they cannot steal clicks from the parent
 * while unmounting. `DialogPanesContext` is reset here so a nested dialog does not inherit pane
 * fill from a parent `DialogPanes` through the portal.
 */
export function DialogContent({
  size = "md",
  height = "auto",
  density = "comfortable",
  ...props
}: DialogContentProps) {
  return (
    <BaseDialog.Portal>
      <BaseDialog.Backdrop
        forceRender
        // Match Viewport: while closing, `open` is false but the portal is still mounted.
        // A force-rendered nested scrim is `fixed inset-0 z-50` — without this it keeps
        // eating clicks on the parent dialog.
        style={(state) => (state.open ? undefined : { pointerEvents: "none" })}
        render={<Backdrop />}
      />
      <BaseDialog.Viewport render={<DialogViewport />}>
        <DialogSizeContext.Provider value={size}>
          <DialogDensityContext.Provider value={density}>
            {/* Portals keep React context. A nested dialog inside DialogPanes would otherwise
                inherit `inPanes` and stretch a content-sized body toward the popup max-height. */}
            <DialogPanesContext.Provider value={false}>
              <BaseDialog.Popup {...props} render={<DialogPopup size={size} height={height} />} />
            </DialogPanesContext.Provider>
          </DialogDensityContext.Provider>
        </DialogSizeContext.Provider>
      </BaseDialog.Viewport>
    </BaseDialog.Portal>
  );
}
