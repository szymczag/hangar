import { ToolbarItemLabel, type ToolbarItemLabelProps } from "./toolbar-item-label";

export type ToolbarMenuTriggerLabelProps = ToolbarItemLabelProps;

/** Alias of `ToolbarItemLabel` kept for the menu-trigger anatomy name (e.g. "Text", "Aa"). */
export function ToolbarMenuTriggerLabel(props: ToolbarMenuTriggerLabelProps) {
  return <ToolbarItemLabel {...props} />;
}
