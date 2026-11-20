import { Menu as BaseMenu } from "@base-ui/react/menu";
import type * as React from "react";

import {
  MenuItem as MenuItemElement,
  type MenuItemVariant,
  MenuItemContent,
  MenuItemDescription,
  MenuItemSecondaryText,
  MenuItemIndicator,
  MenuItemTitle,
  MenuItemTitleRow,
  MenuItemTrailing,
} from "../../elements/menu";
import { TickOutline } from "../../icons";
import { rendersContent } from "../../internal/renders-content";

export type MenuItemProps = Omit<
  BaseMenu.Item.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Element the row renders as, when a `<div>` is not the right one — e.g. `render={<a href=… />}`
   * for a row that navigates. The row's own styling and menu behavior still apply. Narrower than
   * Base UI's `render`: the styled row is the graft target, so a state-aware render function has no
   * row state to receive.
   */
  render?: React.ReactElement;
  /**
   * Row look. `neutral` is the standard text hierarchy, `accent` marks the primary action, and
   * `danger` marks a destructive one.
   *
   * @default "neutral"
   */
  variant?: MenuItemVariant;
  /** Leading element before the label, e.g. `<Icon icon={Settings} tint="secondary" />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Muted secondary line under the label. */
  description?: string;
  /** Muted text shown inline after the label. */
  secondaryText?: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
  /**
   * Single-select selected state. Pass it on **every** row of a single-select list (`true` or
   * `false`) so each row reserves the trailing check gutter and its labels stay a common width;
   * omit it entirely on plain action rows, which then render no gutter.
   *
   * Passing it also makes the row a `menuitemradio` with `aria-checked`, so the current value is
   * announced rather than left to the check glyph. That is why the boolean must be real on every
   * row of the set: a mix of `selected` and omitted rows produces a mix of `menuitemradio` and
   * `menuitem`, which reads as one radio in a list of commands.
   */
  selected?: boolean;
};

/**
 * The ready-made selectable menu row: grafts Base UI's `Menu.Item` behavior onto the styled
 * `MenuItem` and lays out an optional leading icon, the label, a secondary line, the single-select
 * check, and trailing content.
 */
export function MenuItem({
  variant,
  icon,
  description,
  secondaryText,
  trailing,
  selected,
  label,
  render,
  ...props
}: MenuItemProps) {
  // The taller, top-aligned row layout is implied by having a description — derived, not a prop.
  const layout = description ? "stacked" : "single";
  // A row that takes a `selected` boolean is one of a set of mutually exclusive choices, so it is a
  // radio, not a plain command — otherwise the check gutter is the ONLY signal that a value is
  // current and a screen reader hears N equivalent items. Base UI hardcodes `role: "menuitem"` in
  // the item's own props, which `mergeProps` applies leftmost-first, so an explicit role here wins.
  // A consumer that passes its own `role` still wins over this.
  const selectionProps =
    selected === undefined ? undefined : { role: "menuitemradio", "aria-checked": selected };
  return (
    // The consumer's `render` is threaded into the styled row rather than passed to `BaseMenu.Item`:
    // this component's own `render` is what Base UI grafts onto, so a forwarded one would be
    // overwritten. `MenuItemElement` re-renders it as the final element, keeping the row's styling.
    <BaseMenu.Item
      {...selectionProps}
      {...props}
      render={<MenuItemElement layout={layout} variant={variant} render={render} />}
    >
      {icon}
      <MenuItemContent>
        <MenuItemTitleRow>
          <MenuItemTitle>{label}</MenuItemTitle>
          {secondaryText ? <MenuItemSecondaryText>{secondaryText}</MenuItemSecondaryText> : null}
        </MenuItemTitleRow>
        {description ? <MenuItemDescription>{description}</MenuItemDescription> : null}
      </MenuItemContent>
      {/* A single-select list passes a real `selected` boolean on EVERY row; a plain action row
          passes none. Render the check gutter only for the former — and for every row, so a
          selection change never re-truncates a label (keepMounted-equivalent, like Select/
          Combobox's `ItemIndicator`). It trails the label rather than leading it, and sits BEFORE
          `trailing` so a shortcut or count keeps the row's outer edge. Base UI has no
          `Menu.ItemIndicator` to set the attribute, so `data-selected` is set here from the
          boolean; `itemIndicatorClass` hides the glyph via `not-data-selected:invisible` without
          collapsing the reserved column. The glyph is decoration — `aria-checked` on the row above
          is what actually carries the state. */}
      {selected !== undefined ? (
        <MenuItemIndicator data-selected={selected ? "" : undefined}>
          <TickOutline />
        </MenuItemIndicator>
      ) : null}
      {rendersContent(trailing) ? <MenuItemTrailing>{trailing}</MenuItemTrailing> : null}
    </BaseMenu.Item>
  );
}
