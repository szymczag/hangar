import { Menu as BaseMenu } from "@base-ui/react/menu";
import type * as React from "react";

import {
  MenuCheckboxItem as MenuCheckboxItemElement,
  MenuCheckboxItemIndicator,
  MenuItemContent,
  MenuItemControl,
  MenuItemTrailing,
  MenuItemTitle,
  MenuItemTitleRow,
  type MenuItemVariant,
} from "../../elements/menu";
import { TickOutline } from "../../icons";
import { rendersContent } from "../../internal/renders-content";

export type MenuCheckboxItemProps = Omit<
  BaseMenu.CheckboxItem.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: MenuItemVariant;
  /** Leading element shown after the checkbox, e.g. `<Icon icon={Settings} tint="secondary" />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
};

/**
 * The ready-made toggleable multi-select menu row: grafts Base UI's `Menu.CheckboxItem` behavior
 * onto the styled `MenuCheckboxItem` and lays out the checkbox box (a kept-mounted
 * `Menu.CheckboxItemIndicator` grafted onto `MenuCheckboxItemIndicator` + `TickOutline`), optional
 * leading icon, label, and end content. Base UI's `Menu.CheckboxItem` tracks the checked state, so
 * `checked` / `defaultChecked` / `onCheckedChange` forward straight to it and the indicator reads
 * it from context.
 */
export function MenuCheckboxItem({
  variant,
  icon,
  label,
  trailing,
  ...props
}: MenuCheckboxItemProps) {
  return (
    <BaseMenu.CheckboxItem {...props} render={<MenuCheckboxItemElement variant={variant} />}>
      <MenuItemControl>
        <BaseMenu.CheckboxItemIndicator keepMounted render={<MenuCheckboxItemIndicator />}>
          <TickOutline aria-hidden />
        </BaseMenu.CheckboxItemIndicator>
      </MenuItemControl>
      {icon}
      <MenuItemContent>
        <MenuItemTitleRow>
          <MenuItemTitle>{label}</MenuItemTitle>
        </MenuItemTitleRow>
      </MenuItemContent>
      {rendersContent(trailing) ? <MenuItemTrailing>{trailing}</MenuItemTrailing> : null}
    </BaseMenu.CheckboxItem>
  );
}
