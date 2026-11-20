import * as React from "react";

import { type TabsAppearance, type TabsLayout, type TabsStretch } from "../../elements/tabs";

/**
 * Set by the components `Tabs` so the `TabsList`/`Tab`s inside share the set's `variant`. Lives in
 * the components tier: a context is cross-tree coordination — composition — not a single-element
 * `elements` concern.
 */
export const TabsAppearanceContext = React.createContext<TabsAppearance>("contained");

/** Set by the components `Tabs` so the `TabsList`/`Tab`s inside share the set's `stretch` axis. */
export const TabsStretchContext = React.createContext<TabsStretch>("auto");

/** Set by the components `Tabs` so its root and panels share the set's height layout. */
export const TabsLayoutContext = React.createContext<TabsLayout>("content");
