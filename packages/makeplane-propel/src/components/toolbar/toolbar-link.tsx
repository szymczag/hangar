import { Toolbar as BaseToolbar } from "@base-ui/react/toolbar";
import * as React from "react";

import {
  ToolbarLink as ToolbarLinkElement,
  ToolbarItemLabel,
  type ToolbarLinkProps as ToolbarLinkElementProps,
  type ToolbarSize,
} from "../../elements/toolbar";
import { ToolbarSizeContext } from "./toolbar-context";

type ToolbarLinkOwnProps = Omit<
  BaseToolbar.Link.Props,
  "children" | "className" | "style" | "render" | "aria-label"
> & {
  /** Size override; defaults to the surrounding `Toolbar`'s size. */
  size?: ToolbarSize;
  /** Custom render for the underlying styled toolbar link (e.g. a router `Link`). */
  render?: ToolbarLinkElementProps["render"];
};

/**
 * Either a labeled item or an icon-only one — and the accessible name is required either way. A
 * labeled link is named by its visible text (`aria-label` optional); an icon-only one (no `label`)
 * MUST be named by `aria-label` and pass an `icon`, so omitting both is a type error rather than a
 * silently unnamed control.
 */
export type ToolbarLinkProps = ToolbarLinkOwnProps &
  (
    | {
        /** Visible text after the icon (e.g. "History"); widens the square icon box to fit. */
        label: string;
        /** Accessible name; omit to use the visible `label`. */
        "aria-label"?: string;
        /** Icon element rendered inside the toolbar link. */
        icon?: React.ReactNode;
      }
    | {
        label?: undefined;
        /** Accessible name for the icon link. */
        "aria-label": string;
        /** Icon element rendered inside the toolbar link. */
        icon: React.ReactNode;
      }
  );

/**
 * A toolbar item that navigates — Base UI's `Toolbar.Link` (`<a>` in the roving tab order) grafted
 * onto the toolbar item chrome. Pass an icon element, e.g. `<Icon icon={ExternalLink} />`. An
 * `aria-label` is required when the item is icon-only.
 */
export function ToolbarLink({ size, icon, label, render, ...props }: ToolbarLinkProps) {
  const toolbarSize = React.useContext(ToolbarSizeContext);
  return (
    <BaseToolbar.Link
      {...props}
      render={<ToolbarLinkElement size={size ?? toolbarSize} labeled={!!label} render={render} />}
    >
      {icon}
      {label && <ToolbarItemLabel>{label}</ToolbarItemLabel>}
    </BaseToolbar.Link>
  );
}
