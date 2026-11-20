import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";

import {
  ToolbarSeparator as ToolbarSeparatorElement,
  type ToolbarSeparatorProps as ToolbarSeparatorElementProps,
} from "../../elements/toolbar";

export type ToolbarSeparatorProps = Omit<
  BaseToolbar.Separator.Props,
  // Always a vertical rule between items in the horizontal toolbar — not a free orientation axis.
  "className" | "style" | "render" | "orientation"
> & {
  /** Custom render for the underlying styled toolbar separator. */
  render?: ToolbarSeparatorElementProps["render"];
};

/**
 * A thin vertical rule that visually divides one cluster of controls from the next: grafts Base
 * UI's `Toolbar.Separator` behavior (the `separator` role) onto the styled rule.
 */
export function ToolbarSeparator({ render, ...props }: ToolbarSeparatorProps) {
  return (
    <BaseToolbar.Separator
      {...props}
      orientation="vertical"
      render={<ToolbarSeparatorElement render={render} />}
    />
  );
}
