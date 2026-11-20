import { Tabs as BaseTabs } from "@base-ui/react/tabs";

import {
  Tabs as TabsElement,
  type TabsAppearance,
  type TabsLayout,
  type TabsStretch,
} from "../../elements/tabs";
import { TabsAppearanceContext, TabsLayoutContext, TabsStretchContext } from "./tabs-context";

export type TabsProps = Omit<BaseTabs.Root.Props, "className" | "render" | "style"> & {
  /** Whether the set is a contained pill or a flat underline strip. Shared with its parts. */
  variant: TabsAppearance;
  /**
   * Whether the tab row shrinks to fit its tabs or fills its container, splitting it into
   * equal-width tabs. Shared with its parts. Most visible on the `contained` look.
   *
   * @default "auto"
   */
  stretch?: TabsStretch;
  /**
   * Whether the set takes its content height or fills a bounded parent with flexible panels.
   *
   * @default "content"
   */
  layout?: TabsLayout;
};

/**
 * The ready-made tab set: grafts the Base UI `Tabs.Root` behavior onto the styled `elements/tabs`
 * root and shares its `variant`/`stretch` with the `TabsList`/`Tab`s and its `layout` with the
 * `TabsPanel`s inside via context, so you don't repeat them.
 */
export function Tabs({ variant, layout = "content", stretch = "auto", ...props }: TabsProps) {
  return (
    <TabsAppearanceContext.Provider value={variant}>
      <TabsStretchContext.Provider value={stretch}>
        <TabsLayoutContext.Provider value={layout}>
          <BaseTabs.Root
            {...props}
            render={<TabsElement variant={variant} layout={layout} stretch={stretch} />}
          />
        </TabsLayoutContext.Provider>
      </TabsStretchContext.Provider>
    </TabsAppearanceContext.Provider>
  );
}
