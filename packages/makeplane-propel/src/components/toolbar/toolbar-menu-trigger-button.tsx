import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";
import * as React from "react";

import {
  ToolbarMenuTriggerButton as ToolbarMenuTriggerButtonElement,
  type ToolbarMenuTriggerButtonProps as ToolbarMenuTriggerButtonElementProps,
  type ToolbarSize,
} from "../../elements/toolbar";
import { ToolbarSizeContext } from "./toolbar-context";

export type ToolbarMenuTriggerButtonProps = Omit<
  BaseToolbar.Button.Props,
  "className" | "style" | "render"
> & {
  /** Size override; defaults to the surrounding `Toolbar`'s size. */
  size?: ToolbarSize;
  /**
   * Custom render for the styled trigger (e.g. `render={<Menu.Trigger />}` so the menu trigger
   * grafts onto the same focusable control).
   */
  render?: ToolbarMenuTriggerButtonElementProps["render"];
};

/**
 * A toolbar menu-trigger button: grafts Base UI's `Toolbar.Button` (roving-focus item) behavior
 * onto the styled `ToolbarMenuTriggerButton`, taking its `size` from the surrounding `Toolbar`.
 */
export function ToolbarMenuTriggerButton({
  size,
  render,
  ...props
}: ToolbarMenuTriggerButtonProps) {
  const toolbarSize = React.useContext(ToolbarSizeContext);
  return (
    <BaseToolbar.Button
      {...props}
      render={<ToolbarMenuTriggerButtonElement size={size ?? toolbarSize} render={render} />}
    />
  );
}
