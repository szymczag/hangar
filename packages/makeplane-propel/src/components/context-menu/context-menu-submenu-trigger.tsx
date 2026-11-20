import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

import {
  ContextMenuItemLabel,
  ContextMenuSubmenuTrigger as ContextMenuSubmenuTriggerElement,
  type ContextMenuSubmenuTriggerVariant,
} from "../../elements/context-menu";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";

export type ContextMenuSubmenuTriggerProps = Omit<
  BaseContextMenu.SubmenuTrigger.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action.
   *
   * @default "neutral"
   */
  variant?: ContextMenuSubmenuTriggerVariant;
  /** Leading element before the label, e.g. `<Icon icon={Folder} />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Content pinned before the submenu caret, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
};

/**
 * The ready-made submenu trigger: grafts Base UI's `SubmenuTrigger` behavior onto the styled
 * `ContextMenuSubmenuTrigger` and composes its region parts — a leading icon, the label, optional
 * trailing content, and the caret that points toward the submenu.
 */
export function ContextMenuSubmenuTrigger({
  variant,
  icon,
  trailing,
  label,
  ...props
}: ContextMenuSubmenuTriggerProps) {
  return (
    <BaseContextMenu.SubmenuTrigger
      {...props}
      render={<ContextMenuSubmenuTriggerElement variant={variant} />}
    >
      {icon}
      <ContextMenuItemLabel>{label}</ContextMenuItemLabel>
      {trailing}
      <DisclosureIndicator motion="pointEnd" tint="tertiary">
        <ChevronDownOutline />
      </DisclosureIndicator>
    </BaseContextMenu.SubmenuTrigger>
  );
}
