import { Menu as BaseMenu } from "@base-ui/react/menu";
import type * as React from "react";

import {
  MenuItemContent,
  MenuItemControl,
  MenuItemTrailing,
  MenuItemTitle,
  MenuItemTitleRow,
  type MenuItemVariant,
  MenuRadioItem as MenuRadioItemElement,
  MenuRadioItemCheck,
  MenuRadioItemIndicator,
} from "../../elements/menu";
import { TickOutline } from "../../icons";
import { useMenuRadioMarker } from "../../internal/menu-radio-marker";
import { RadioDot } from "../../internal/radio-dot";
import { rendersContent } from "../../internal/renders-content";

export type MenuRadioItemProps = Omit<
  BaseMenu.RadioItem.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: MenuItemVariant;
  /**
   * Leading element, e.g. `<Icon icon={Settings} tint="secondary" />`. With the group's
   * `marker="radio"` it sits after the ring; with the default tick it leads the row.
   */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
};

/**
 * The ready-made single-select menu row: grafts Base UI's `Menu.RadioItem` behavior onto the styled
 * `MenuRadioItem` and marks the current row the way its `MenuRadioGroup`'s `marker` says. `check`
 * (the default): a kept-mounted trailing tick (`Menu.RadioItemIndicator` grafted onto
 * `MenuRadioItemCheck`) that shows on the selected row, the same mark every other single-select row
 * in the library uses. `radio`: a leading ring (`MenuRadioItemIndicator` in a `MenuItemControl`
 * gutter) drawn on every row with only its inner dot hiding, for a popup that also holds a checkbox
 * group and needs the two kinds of choice told apart. `keepMounted` is load-bearing either way: the
 * indicator holds its slot and carries `data-checked` / `data-unchecked` for the styling to key
 * off. Wrap rows in a `MenuRadioGroup` carrying `value`/`onValueChange`; both the selected state
 * and the marker come from context.
 */
export function MenuRadioItem({ variant, icon, label, trailing, ...props }: MenuRadioItemProps) {
  const marker = useMenuRadioMarker();

  return (
    <BaseMenu.RadioItem {...props} render={<MenuRadioItemElement variant={variant} />}>
      {marker === "radio" ? (
        <MenuItemControl>
          <BaseMenu.RadioItemIndicator keepMounted render={<MenuRadioItemIndicator />}>
            <RadioDot aria-hidden />
          </BaseMenu.RadioItemIndicator>
        </MenuItemControl>
      ) : null}
      {icon}
      <MenuItemContent>
        <MenuItemTitleRow>
          <MenuItemTitle>{label}</MenuItemTitle>
        </MenuItemTitleRow>
      </MenuItemContent>
      {marker === "check" ? (
        <BaseMenu.RadioItemIndicator keepMounted render={<MenuRadioItemCheck />}>
          <TickOutline aria-hidden />
        </BaseMenu.RadioItemIndicator>
      ) : null}
      {rendersContent(trailing) ? <MenuItemTrailing>{trailing}</MenuItemTrailing> : null}
    </BaseMenu.RadioItem>
  );
}
