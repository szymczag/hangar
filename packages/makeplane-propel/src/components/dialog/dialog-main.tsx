import * as React from "react";

import {
  DialogMain as DialogMainElement,
  type DialogMainProps as DialogMainElementProps,
} from "../../elements/dialog/dialog-main";
import { DialogDensityContext, DialogPanesContext, DialogSizeContext } from "./dialog-context";

export type DialogMainProps = Omit<DialogMainElementProps, "size" | "density" | "inPanes">;

/**
 * The padded top section of the dialog popup: optional `DialogProgression`, `DialogHeader` /
 * `DialogHeading`, and the scrollable `DialogBody`. Its gutter follows the `size` chosen on
 * `DialogContent` (16 px, 48 px at `full`); `density="compact"` keeps 16 px at `full`. Inside
 * `DialogPanes` it fills the width beside `DialogAside`.
 */
export function DialogMain(props: DialogMainProps) {
  const size = React.useContext(DialogSizeContext);
  const density = React.useContext(DialogDensityContext);
  const inPanes = React.useContext(DialogPanesContext);
  return <DialogMainElement size={size} density={density} inPanes={inPanes} {...props} />;
}
