import { AlertDialog as BaseAlertDialog } from "@base-ui/react/alert-dialog";

import { AlertDialogDescription as AlertDialogDescriptionElement } from "../../elements/alert-dialog/alert-dialog-description";

export type AlertDialogDescriptionProps = Omit<
  BaseAlertDialog.Description.Props,
  "className" | "style"
>;

/**
 * The supporting description for the alert dialog. Base UI links it to the popup via
 * `aria-describedby`; the styled `elements` description supplies the body-sm / secondary look.
 * Defaults to a paragraph. Pass `render={<div />}` for block content such as an impact list; both
 * the description styling and Base UI accessibility wiring are preserved.
 */
export function AlertDialogDescription({ render, ...props }: AlertDialogDescriptionProps) {
  return (
    <BaseAlertDialog.Description
      {...props}
      render={<AlertDialogDescriptionElement render={render} />}
    />
  );
}
