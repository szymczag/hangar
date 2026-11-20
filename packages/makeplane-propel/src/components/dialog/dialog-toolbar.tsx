import * as React from "react";

import {
  DialogToolbar as DialogToolbarElement,
  type DialogToolbarProps as DialogToolbarElementProps,
} from "../../elements/dialog/dialog-toolbar";
import { DialogDensityContext, DialogSizeContext } from "./dialog-context";

export type DialogToolbarProps = Omit<DialogToolbarElementProps, "size" | "density">;

/**
 * Top chrome of the dialog popup, sibling of `DialogMain`. Its start gutter follows the `size`
 * chosen on `DialogContent` (16 px, 48 px at `full`); the end gutter is 40 px so an end-aligned
 * control clears the corner dismiss. `density="compact"` keeps 16 px start at `full`. Bottom border
 * is flush to the popup, matching `DialogActions`.
 */
export function DialogToolbar(props: DialogToolbarProps) {
  const size = React.useContext(DialogSizeContext);
  const density = React.useContext(DialogDensityContext);
  return <DialogToolbarElement size={size} density={density} {...props} />;
}
