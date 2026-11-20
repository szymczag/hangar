import { Toggle } from "@base-ui/react/toggle";
import type { Toggle as BaseToggleTypes } from "@base-ui/react/toggle";
import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";
import * as React from "react";

import {
  ToolbarButton as ToolbarButtonElement,
  ToolbarItemLabel,
  type ToolbarButtonProps as ToolbarButtonElementProps,
  type ToolbarSize,
} from "../../elements/toolbar";
import { ToolbarSizeContext } from "./toolbar-context";

type ToolbarToggleOwnProps<Value extends string = string> = Omit<
  BaseToggleTypes.Props<Value>,
  "children" | "className" | "style" | "render" | "aria-label"
> & {
  /** Size override; defaults to the surrounding `Toolbar`'s size. */
  size?: ToolbarSize;
  /** Custom render for the underlying styled toolbar button. */
  render?: ToolbarButtonElementProps["render"];
};

/**
 * Either a labeled item or an icon-only one — and the accessible name is required either way. A
 * labeled toggle is named by its visible text (`aria-label` optional); an icon-only one (no
 * `label`) MUST be named by `aria-label` and pass an `icon`, so omitting both is a type error
 * rather than a silently unnamed control.
 */
export type ToolbarToggleProps<Value extends string = string> = ToolbarToggleOwnProps<Value> &
  (
    | {
        /** Visible text after the icon (e.g. "Comment"); widens the square icon box to fit. */
        label: string;
        /** Accessible name; omit to use the visible `label`. */
        "aria-label"?: string;
        /** Icon element rendered inside the toolbar toggle. */
        icon?: React.ReactNode;
      }
    | {
        label?: undefined;
        /** Accessible name for the icon toggle. */
        "aria-label": string;
        /** Icon element rendered inside the toolbar toggle. */
        icon: React.ReactNode;
      }
  );

/**
 * A two-state toolbar button for formatting toggles like bold or italic. Grafts Base UI's
 * `Toolbar.Button` (roving-focus item) and `Toggle` (pressed state) behaviors onto the styled
 * `ToolbarButton`, and takes its `size` from the surrounding `Toolbar` via context.
 */
export function ToolbarToggle<Value extends string = string>({
  render,
  size,
  icon,
  label,
  disabled,
  "aria-label": ariaLabel,
  ...toggleProps
}: ToolbarToggleProps<Value>) {
  const toolbarSize = React.useContext(ToolbarSizeContext);
  return (
    // `disabled` on `Toolbar.Button` so roving-focus metadata matches Button/MenuTrigger;
    // also on `Toggle` so pressed-state and ToggleGroup context stay in sync.
    <BaseToolbar.Button
      disabled={disabled}
      render={
        <Toggle
          {...toggleProps}
          disabled={disabled}
          render={
            <ToolbarButtonElement
              size={size ?? toolbarSize}
              labeled={!!label}
              aria-label={ariaLabel}
              render={render}
            />
          }
        />
      }
    >
      {icon}
      {label && <ToolbarItemLabel>{label}</ToolbarItemLabel>}
    </BaseToolbar.Button>
  );
}
