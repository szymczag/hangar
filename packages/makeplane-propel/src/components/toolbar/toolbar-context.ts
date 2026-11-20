import * as React from "react";

import { type ToolbarSize } from "../../elements/toolbar";

/**
 * Set by the components `Toolbar` so the controls inside share its `size`. Lives in the components
 * tier: a context is cross-tree coordination — composition — not a single-element `elements`
 * concern.
 */
export const ToolbarSizeContext = React.createContext<ToolbarSize>("sm");
