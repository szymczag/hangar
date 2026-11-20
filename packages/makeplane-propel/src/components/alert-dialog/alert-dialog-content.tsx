import { AlertDialog as BaseAlertDialog } from "@base-ui/react/alert-dialog";

import { AlertDialogBackdrop } from "../../elements/alert-dialog/alert-dialog-backdrop";
import {
  AlertDialogPopup,
  type AlertDialogPopupProps,
} from "../../elements/alert-dialog/alert-dialog-popup";
import { AlertDialogViewport } from "../../elements/alert-dialog/alert-dialog-viewport";

export type AlertDialogContentProps = Omit<AlertDialogPopupProps, "render"> &
  Pick<BaseAlertDialog.Popup.Props, "initialFocus" | "finalFocus">;

/**
 * Convenience that composes the alert dialog overlay boilerplate — Base UI portal, the 25% black
 * backdrop, the responsive viewport, and the popup — so a consumer only writes the trigger and the
 * popup body.
 *
 * Initial focus follows Base UI: the first tabbable element in the popup, which in the default
 * anatomy is the first action button (Cancel). Pass `initialFocus` (a ref, or a function of the
 * interaction type) to steer it — for example onto Cancel when a scrollable `AlertDialogBody` with
 * `tabIndex={0}` would otherwise come first in DOM order. `finalFocus` overrides where focus
 * returns on close (default: the trigger).
 *
 * Nested alerts keep their own 25% scrim: Base UI omits a nested Backdrop unless `forceRender` is
 * set, which would leave a confirmation sitting on its parent dialog with no extra overlay. Closed
 * force-rendered backdrops set `pointer-events: none` so they cannot steal clicks from the parent
 * while unmounting.
 */
export function AlertDialogContent(props: AlertDialogContentProps) {
  return (
    <BaseAlertDialog.Portal>
      <BaseAlertDialog.Backdrop
        forceRender
        style={(state) => (state.open ? undefined : { pointerEvents: "none" })}
        render={<AlertDialogBackdrop />}
      />
      <BaseAlertDialog.Viewport render={<AlertDialogViewport />}>
        <BaseAlertDialog.Popup {...props} render={<AlertDialogPopup />} />
      </BaseAlertDialog.Viewport>
    </BaseAlertDialog.Portal>
  );
}
