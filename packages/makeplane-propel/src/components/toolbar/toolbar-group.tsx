import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";

import {
  ToolbarGroup as ToolbarGroupElement,
  type ToolbarGroupProps as ToolbarGroupElementProps,
} from "../../elements/toolbar";

export type ToolbarGroupProps = Omit<BaseToolbar.Group.Props, "className" | "style" | "render"> & {
  /** Custom render for the underlying styled toolbar group. */
  render?: ToolbarGroupElementProps["render"];
};

/**
 * Groups related controls: grafts Base UI's `Toolbar.Group` behavior (the `group` role + group
 * `disabled`) onto the styled `ToolbarGroup` cluster. The group shares the toolbar row's `gap-2`
 * per Figma, so it is a semantic grouping — pair it with `ToolbarSeparator`s to make it visible.
 */
export function ToolbarGroup({ render, ...props }: ToolbarGroupProps) {
  return <BaseToolbar.Group {...props} render={<ToolbarGroupElement render={render} />} />;
}
