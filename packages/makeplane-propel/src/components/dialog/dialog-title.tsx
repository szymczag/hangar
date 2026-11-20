import { Dialog as BaseDialog } from "@base-ui/react/dialog";

import { DialogTitle as DialogTitleElement } from "../../elements/dialog/dialog-title";

export type DialogTitleProps = Omit<BaseDialog.Title.Props, "className" | "style">;

/**
 * The accessible title for the dialog: Base UI's `Dialog.Title` behavior (links to the popup via
 * `aria-labelledby`) grafted onto the dialog-owned title chrome (`text-h5-medium`).
 */
export function DialogTitle(props: DialogTitleProps) {
  return <BaseDialog.Title {...props} render={<DialogTitleElement />} />;
}
