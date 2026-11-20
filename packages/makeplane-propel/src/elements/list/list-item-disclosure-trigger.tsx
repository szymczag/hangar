import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { listItemDisclosureTriggerVariants } from "./variants";

export type ListItemDisclosureTriggerProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style"
>;

/**
 * The styled expand/collapse control at a row's trailing edge — a `<button>`, sibling to the row's
 * primary. Base-UI-agnostic — graft `Collapsible.Trigger` behavior in `components` via
 * `<BaseCollapsible.Trigger render={<ListItemDisclosureTrigger/>} />`. Compose a
 * `DisclosureIndicator` inside.
 */
export function ListItemDisclosureTrigger({ render, ...props }: ListItemDisclosureTriggerProps) {
  const defaultProps: useRender.ElementProps<"button"> & { "data-disclosure-trigger": "" } = {
    type: "button",
    "data-disclosure-trigger": "",
    className: listItemDisclosureTriggerVariants(),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
