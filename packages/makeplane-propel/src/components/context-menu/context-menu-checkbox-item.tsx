import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

import {
  ContextMenuCheckboxItem as ContextMenuCheckboxItemElement,
  ContextMenuCheckboxItemIndicator,
  ContextMenuItemLabel,
  type ContextMenuItemVariant,
} from "../../elements/context-menu";
import { TickOutline } from "../../icons";

export type ContextMenuCheckboxItemProps = Omit<
  BaseContextMenu.CheckboxItem.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action.
   *
   * @default "neutral"
   */
  variant?: ContextMenuItemVariant;
  /** Leading element after the tick, e.g. `<Icon icon={Columns} />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
};

/**
 * The ready-made toggleable context-menu row: grafts Base UI's `CheckboxItem` behavior onto the
 * styled row and bakes a kept-mounted tick indicator, so `checked` / `defaultChecked` /
 * `onCheckedChange` forward straight to Base UI and the tick reads state from context.
 */
export function ContextMenuCheckboxItem({
  variant,
  icon,
  trailing,
  label,
  ...props
}: ContextMenuCheckboxItemProps) {
  return (
    <BaseContextMenu.CheckboxItem
      {...props}
      render={<ContextMenuCheckboxItemElement variant={variant} />}
    >
      <BaseContextMenu.CheckboxItemIndicator
        keepMounted
        render={<ContextMenuCheckboxItemIndicator />}
      >
        <TickOutline aria-hidden />
      </BaseContextMenu.CheckboxItemIndicator>
      {icon}
      <ContextMenuItemLabel>{label}</ContextMenuItemLabel>
      {trailing}
    </BaseContextMenu.CheckboxItem>
  );
}
