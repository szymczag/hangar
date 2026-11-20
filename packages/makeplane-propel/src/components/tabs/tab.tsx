import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import * as React from "react";

import {
  Tab as TabElement,
  TabUnderlineBar,
  TabUnderlineBarTrack,
  TabUnderlineLabel,
} from "../../elements/tabs";
import { TabsAppearanceContext, TabsStretchContext } from "./tabs-context";

export type TabProps = Omit<BaseTabs.Tab.Props, "children" | "className" | "style"> & {
  /** Element rendered before the label (inline-start), e.g. `<Icon icon={Folder} />`. */
  icon?: React.ReactNode;
  /** Visible tab label. */
  label: string;
};

/**
 * The ready-made tab button: grafts the Base UI `Tabs.Tab` behavior onto the styled `elements/tabs`
 * tab (taking the set's `variant`/`stretch` from context, so you don't pass them) and lays out an
 * optional `icon` with the label. The `underline` variant additionally renders the sliding bar
 * track beneath the label. A consumer `render` target is composed through the styled tab,
 * preserving Propel's classes; render callbacks receive the original Base UI tab state.
 */
export function Tab({ icon, label, render, ...props }: TabProps) {
  const variant = React.useContext(TabsAppearanceContext);
  const stretch = React.useContext(TabsStretchContext);
  const composedRender: BaseTabs.Tab.Props["render"] =
    typeof render === "function" ? (
      (renderProps, state) => (
        <TabElement variant={variant} stretch={stretch} render={render(renderProps, state)} />
      )
    ) : (
      <TabElement variant={variant} stretch={stretch} render={render} />
    );

  if (variant === "underline") {
    return (
      <BaseTabs.Tab render={composedRender} {...props}>
        <TabUnderlineLabel>
          {icon}
          {label}
        </TabUnderlineLabel>
        <TabUnderlineBarTrack>
          <TabUnderlineBar />
        </TabUnderlineBarTrack>
      </BaseTabs.Tab>
    );
  }

  return (
    <BaseTabs.Tab render={composedRender} {...props}>
      {icon}
      {label}
    </BaseTabs.Tab>
  );
}
