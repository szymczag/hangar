import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import * as React from "react";

import { TabsPanel as TabsPanelElement } from "../../elements/tabs";
import { TabsLayoutContext } from "./tabs-context";

export type TabsPanelProps = Omit<BaseTabs.Panel.Props, "className" | "render" | "style">;

/**
 * The ready-made tab panel: grafts the Base UI `Tabs.Panel` behavior (shown when the `Tab` of the
 * matching `value` is active) onto the styled `elements/tabs` panel and applies the set's height
 * layout from context.
 */
export function TabsPanel(props: TabsPanelProps) {
  const layout = React.useContext(TabsLayoutContext);
  return <BaseTabs.Panel {...props} render={<TabsPanelElement layout={layout} />} />;
}
