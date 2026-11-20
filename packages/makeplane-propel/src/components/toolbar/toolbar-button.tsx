import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";
import * as React from "react";

import {
  ToolbarButton as ToolbarButtonElement,
  ToolbarItemLabel,
  type ToolbarButtonProps as ToolbarButtonElementProps,
  type ToolbarSize,
} from "../../elements/toolbar";
import { ToolbarSizeContext } from "./toolbar-context";

type ToolbarButtonOwnProps = Omit<
  BaseToolbar.Button.Props,
  "children" | "className" | "style" | "render" | "aria-label"
> & {
  /** Size override; defaults to the surrounding `Toolbar`'s size. */
  size?: ToolbarSize;
  /** Custom render for the underlying styled toolbar button. */
  render?: ToolbarButtonElementProps["render"];
};

/**
 * Either a labeled item or an icon-only one — and the accessible name is required either way. A
 * labeled button is named by its visible text (`aria-label` optional); an icon-only one (no
 * `label`) MUST be named by `aria-label` and pass an `icon`, so omitting both is a type error
 * rather than a silently unnamed control.
 */
export type ToolbarButtonProps = ToolbarButtonOwnProps &
  (
    | {
        /** Visible text after the icon (e.g. "Comment"); widens the square icon box to fit. */
        label: string;
        /** Accessible name; omit to use the visible `label`. */
        "aria-label"?: string;
        /** Icon element rendered inside the toolbar button. */
        icon?: React.ReactNode;
      }
    | {
        label?: undefined;
        /** Accessible name for the icon button. */
        "aria-label": string;
        /** Icon element rendered inside the toolbar button. */
        icon: React.ReactNode;
      }
  );

/**
 * A toolbar action button: grafts Base UI's `Toolbar.Button` (roving-focus item) behavior onto the
 * styled `ToolbarButton`, taking its `size` from the surrounding `Toolbar` via context.
 */
export function ToolbarButton({ size, icon, label, render, ...props }: ToolbarButtonProps) {
  const toolbarSize = React.useContext(ToolbarSizeContext);
  return (
    <BaseToolbar.Button
      {...props}
      render={<ToolbarButtonElement size={size ?? toolbarSize} labeled={!!label} render={render} />}
    >
      {icon}
      {label && <ToolbarItemLabel>{label}</ToolbarItemLabel>}
    </BaseToolbar.Button>
  );
}
