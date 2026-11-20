import * as React from "react";

import { type DialogDensity } from "../../elements/dialog/dialog-main";
import { type DialogPopupSize } from "../../elements/dialog/dialog-popup";

/**
 * The popup `size` chosen on `DialogContent`, read by the ready-made `DialogMain`, `DialogActions`,
 * `DialogToolbar`, and `DialogAside` so their gutter follows the popup without a prop at every call
 * site (rules 7, 13). Defaults to the popup's own default.
 */
export const DialogSizeContext = React.createContext<DialogPopupSize>("md");

/**
 * Compactness chosen on `DialogContent`. `comfortable` (default) lets `size` pick the gutter;
 * `compact` keeps 16 px at every size, including `full`. Ready-mades read it and pass it down
 * (rules 7, 13).
 */
export const DialogDensityContext = React.createContext<DialogDensity>("comfortable");

/**
 * True while rendering inside the ready-made `DialogPanes`. `DialogMain` reads it and passes
 * `inPanes` as a prop so the pane child can fill the row (rule 7). `DialogContent` resets this to
 * `false` so a nested dialog does not inherit the parent's pane fill through the portal.
 */
export const DialogPanesContext = React.createContext(false);
