import * as React from "react";

import {
  DialogPanes as DialogPanesElement,
  type DialogPanesProps,
} from "../../elements/dialog/dialog-panes";
import { DialogPanesContext } from "./dialog-context";

export type { DialogPanesProps };

/**
 * The side-by-side row of a two-pane dialog: `DialogAside` on the start side, `DialogMain` filling
 * the rest. Marks its descendants so the ready-made `DialogMain` fills the row (rule 7).
 */
export function DialogPanes(props: DialogPanesProps) {
  return (
    <DialogPanesContext.Provider value={true}>
      <DialogPanesElement {...props} />
    </DialogPanesContext.Provider>
  );
}
