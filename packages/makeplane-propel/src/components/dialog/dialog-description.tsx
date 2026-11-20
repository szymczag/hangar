import { Dialog as BaseDialog } from "@base-ui/react/dialog";

import { DialogDescription as DialogDescriptionElement } from "../../elements/dialog/dialog-description";

export type DialogDescriptionProps = Omit<BaseDialog.Description.Props, "className" | "style">;

/**
 * The supporting description for the dialog: Base UI's `Dialog.Description` behavior (links to the
 * popup via `aria-describedby`) grafted onto the dialog-owned description chrome (`text-body-xs`
 * tertiary).
 */
export function DialogDescription(props: DialogDescriptionProps) {
  return <BaseDialog.Description {...props} render={<DialogDescriptionElement />} />;
}
