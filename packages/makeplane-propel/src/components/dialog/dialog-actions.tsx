import * as React from "react";

import {
  DialogActions as DialogActionsElement,
  type DialogActionsProps as DialogActionsElementProps,
} from "../../elements/dialog/dialog-actions";
import { DialogDensityContext, DialogSizeContext } from "./dialog-context";

export type DialogActionsProps = Omit<DialogActionsElementProps, "size" | "density">;

/**
 * The footer of the dialog popup: an optional `DialogInfo` at the inline-start, then action
 * buttons. Its gutter follows the `size` chosen on `DialogContent` (16 px, 48 × 18 px at `full`);
 * `density="compact"` keeps 16 px at `full`. Stays visible while `DialogBody` scrolls.
 */
export function DialogActions(props: DialogActionsProps) {
  const size = React.useContext(DialogSizeContext);
  const density = React.useContext(DialogDensityContext);
  return <DialogActionsElement size={size} density={density} {...props} />;
}
