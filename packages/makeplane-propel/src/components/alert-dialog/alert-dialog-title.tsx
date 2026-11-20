import { AlertDialog as BaseAlertDialog } from "@base-ui/react/alert-dialog";

import { AlertDialogTitle as AlertDialogTitleElement } from "../../elements/alert-dialog/alert-dialog-title";

export type AlertDialogTitleProps = Omit<BaseAlertDialog.Title.Props, "className" | "style">;

/**
 * The accessible title for the alert dialog. Base UI links it to the popup via `aria-labelledby`;
 * the styled `elements` title supplies the h6/semibold look.
 */
export function AlertDialogTitle(props: AlertDialogTitleProps) {
  return <BaseAlertDialog.Title {...props} render={<AlertDialogTitleElement />} />;
}
