import { AlertDialog as BaseAlertDialog } from "@base-ui/react/alert-dialog";

export type AlertDialogProps = Omit<BaseAlertDialog.Root.Props, "className" | "style">;

/**
 * Modal confirmation root. Escape dismisses the topmost alert as a cancellation, matching Plane's
 * existing behavior. Outside presses do not dismiss it. Consumers can veto a close through
 * `onOpenChange` and `details.cancel()`, for example while a request is pending.
 *
 * Base UI owns focus trapping, nested dismissal, and focus restoration. Explicit close controls,
 * `actionsRef.close()`, and controlled `open` state remain available.
 */
export function AlertDialog(props: AlertDialogProps) {
  return <BaseAlertDialog.Root {...props} />;
}
