import * as React from "react";

import {
  DialogAside as DialogAsideElement,
  type DialogAsideProps as DialogAsideElementProps,
} from "../../elements/dialog/dialog-aside";
import { DialogDensityContext, DialogSizeContext } from "./dialog-context";

export type DialogAsideProps = Omit<DialogAsideElementProps, "size" | "density">;

/**
 * A 280 px start-side column inside `DialogPanes`, beside `DialogMain`. Stretches to the panes'
 * height so its end seam is the full popup. Holds navigation for the dialog's content — a step
 * list, a section list. Its gutter follows the `size` chosen on `DialogContent` (16 px, 48 px at
 * `full`); `density="compact"` keeps 16 px at `full`. Pass `tabIndex={0}` when its content can
 * overflow.
 */
export function DialogAside(props: DialogAsideProps) {
  const size = React.useContext(DialogSizeContext);
  const density = React.useContext(DialogDensityContext);
  return <DialogAsideElement size={size} density={density} {...props} />;
}
