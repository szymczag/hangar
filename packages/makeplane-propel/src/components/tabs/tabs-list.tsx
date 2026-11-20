import { ScrollArea as BaseScrollArea } from "@base-ui/react/scroll-area";
import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import * as React from "react";

import { ScrollAreaScrollbar, ScrollAreaThumb } from "../../elements/scroll-area";
import { TabsList as TabsListElement, TabsListScrollArea } from "../../elements/tabs";
import { TabsAppearanceContext, TabsStretchContext } from "./tabs-context";
import { TabsIndicator } from "./tabs-indicator";

export type TabsListProps = Omit<BaseTabs.List.Props, "className" | "style" | "activateOnFocus"> & {
  /**
   * Whether moving focus to a tab with the arrow keys also activates it immediately (updates
   * `aria-selected` and swaps the panel), vs. only moving focus until committed with Enter/Space.
   * Pass `true` to activate a tab as soon as arrow-key focus reaches it — costs a render/panel-swap
   * per keystroke, so reach for it only when switching tabs is cheap and instant visual feedback
   * matters more than avoiding that cost.
   *
   * @default false
   */
  activateOnFocus?: boolean;
};

/**
 * The ready-made tab strip: grafts the Base UI `ScrollArea.Root` onto the styled
 * `TabsListScrollArea` frame, then grafts the Base UI `Tabs.List` behavior onto the styled
 * `TabsList` (taking the set's `variant`/`stretch` from context) rendered as the scroll viewport,
 * plus a horizontal scrollbar so a long row of tabs scrolls, and renders the active-tab underline
 * `TabsIndicator` for the `underline` variant.
 */
export function TabsList({ children, activateOnFocus = false, ...props }: TabsListProps) {
  const variant = React.useContext(TabsAppearanceContext);
  const stretch = React.useContext(TabsStretchContext);
  return (
    <BaseScrollArea.Root render={<TabsListScrollArea stretch={stretch} />}>
      <BaseTabs.List
        render={
          <BaseScrollArea.Viewport
            render={<TabsListElement variant={variant} stretch={stretch} />}
          />
        }
        activateOnFocus={activateOnFocus}
        {...props}
      >
        {children}
        {variant === "underline" ? <TabsIndicator /> : null}
      </BaseTabs.List>
      <BaseScrollArea.Scrollbar orientation="horizontal" render={<ScrollAreaScrollbar />}>
        <BaseScrollArea.Thumb render={<ScrollAreaThumb />} />
      </BaseScrollArea.Scrollbar>
    </BaseScrollArea.Root>
  );
}
