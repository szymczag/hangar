import { Menu as BaseMenu } from "@base-ui/react/menu";
import type * as React from "react";

import {
  MenuItemContent,
  MenuItemTitle,
  MenuItemTitleRow,
  MenuItemTrailing,
  type MenuItemVariant,
  MenuSubmenuTrigger as MenuSubmenuTriggerElement,
} from "../../elements/menu";
import { ChevronDownOutline } from "../../icons";
import { DisclosureIndicator } from "../../internal/disclosure-indicator";
import { rendersContent } from "../../internal/renders-content";

export type MenuSubmenuTriggerProps = Omit<
  BaseMenu.SubmenuTrigger.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: MenuItemVariant;
  /** Leading element before the label, e.g. `<Icon icon={Folder} tint="secondary" />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /**
   * Content pinned before the submenu chevron, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge
   * />`.
   */
  trailing?: React.ReactNode;
};

/**
 * The ready-made submenu trigger row: grafts Base UI's `Menu.SubmenuTrigger` behavior onto the
 * styled `MenuSubmenuTrigger` and lays out an optional leading icon, label, end content, and the
 * submenu chevron indicator.
 */
export function MenuSubmenuTrigger({
  variant,
  icon,
  trailing,
  label,
  ...props
}: MenuSubmenuTriggerProps) {
  return (
    <BaseMenu.SubmenuTrigger {...props} render={<MenuSubmenuTriggerElement variant={variant} />}>
      {icon}
      <MenuItemContent>
        <MenuItemTitleRow>
          <MenuItemTitle>{label}</MenuItemTitle>
        </MenuItemTitleRow>
      </MenuItemContent>
      {rendersContent(trailing) ? <MenuItemTrailing>{trailing}</MenuItemTrailing> : null}
      <DisclosureIndicator motion="pointEnd" tint="tertiary">
        <ChevronDownOutline />
      </DisclosureIndicator>
    </BaseMenu.SubmenuTrigger>
  );
}
