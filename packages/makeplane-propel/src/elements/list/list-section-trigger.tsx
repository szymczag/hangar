import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ListSectionTriggerVariantProps, listSectionTriggerVariants } from "./variants";

export type ListSectionTriggerProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style"
> &
  ListSectionTriggerVariantProps;

/**
 * A collapsible section's header — a small, muted heading with the chevron pushed to the
 * inline-end. Renders a `<button>` by default and carries the `group` so a `DisclosureIndicator`
 * inside rotates off `data-panel-open`. It does NOT embed any disclosure behavior, keeping
 * `elements/list` independent of the Collapsible primitive: graft Base UI in `components` via
 * `<BaseCollapsible.Trigger render={<ListSectionTrigger />} />` (behavior outer, styled part as the
 * render target — same shape as the ready-made `Collapsible`).
 */
export function ListSectionTrigger({ render, ...props }: ListSectionTriggerProps) {
  return useRender({
    defaultTagName: "button",
    render,
    props: mergeProps({ className: listSectionTriggerVariants(), type: "button" }, props),
  });
}
