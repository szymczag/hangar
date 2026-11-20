import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { toolbarToggleGroupVariants } from "./variants";

export type ToolbarToggleGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * A set of `ToolbarToggle`s that share state. Renders a `<div>` by default and bakes in only the
 * cluster layout, keeping `elements/toolbar` independent of the ToggleGroup primitive: a
 * composition grafts shared-state behavior by hosting this element on Base UI's ToggleGroup —
 * `<ToggleGroup render={<ToolbarToggleGroup />} />` (the styled node is the host).
 */
export function ToolbarToggleGroup({ render, ...props }: ToolbarToggleGroupProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: toolbarToggleGroupVariants() }, props),
  });
}
