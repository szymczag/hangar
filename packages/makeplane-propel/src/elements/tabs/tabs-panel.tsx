import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TabsPanelVariantProps, tabsPanelVariants } from "./variants";

export type { TabsPanelLayout } from "./variants";

export type TabsPanelProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  TabsPanelVariantProps;

/**
 * Content shown when the `Tab` of the matching `value` is active — a single styled `<div>`.
 * Base-UI-agnostic: the ready-made `components/tabs` grafts the Base UI `Tabs.Panel` behavior via
 * `<BaseTabs.Panel render={<TabsPanel/>}/>`.
 */
export function TabsPanel({ layout, render, ...props }: TabsPanelProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: tabsPanelVariants({ layout }) };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
