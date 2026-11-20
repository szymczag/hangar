import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TabsListScrollAreaVariantProps, tabsListScrollAreaVariants } from "./variants";

export type TabsListScrollAreaProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  TabsListScrollAreaVariantProps;

/**
 * The horizontal scroll frame around a `TabsList` — a single styled `<div>` by default. It bakes in
 * NO scroll behavior, keeping `elements/tabs` independent of the ScrollArea primitive: the
 * ready-made `components/tabs` `TabsList` grafts the Base UI `ScrollArea.Root` behavior onto it
 * (`<BaseScrollArea.Root render={<TabsListScrollArea/>}/>`) and composes the list (as the scroll
 * viewport) plus a scrollbar so a long row of tabs scrolls sideways.
 */
export function TabsListScrollArea({ stretch, render, ...props }: TabsListScrollAreaProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: tabsListScrollAreaVariants({ stretch }) }, props),
  });
}
