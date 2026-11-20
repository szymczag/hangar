import { Menu } from "@base-ui/react/menu";

import { ToolbarItemLabel } from "../../elements/toolbar/index";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";
import { ToolbarMenuTriggerButton } from "./toolbar-menu-trigger-button";

export type ToolbarMenuTriggerProps = Omit<
  Menu.Trigger.Props,
  "children" | "className" | "style"
> & {
  /** Visible menu-trigger label. */
  label: string;
};

/** The trigger that opens a `ToolbarMenu`: a label plus a disclosure chevron. */
export function ToolbarMenuTrigger({ render, label, ...props }: ToolbarMenuTriggerProps) {
  // The toolbar item renders as a `Menu.Trigger`; a consumer `render` customizes that
  // inner element (not the wrapping button), so it is nested onto the trigger.
  return (
    <ToolbarMenuTriggerButton render={<Menu.Trigger render={render} />} {...props}>
      <ToolbarItemLabel>{label}</ToolbarItemLabel>
      <DisclosureIndicator motion="flip" tint="secondary">
        <ChevronDownOutline />
      </DisclosureIndicator>
    </ToolbarMenuTriggerButton>
  );
}
