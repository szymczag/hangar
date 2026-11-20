import { ContextMenu as BaseContextMenu } from "@base-ui/react/context-menu";
import type * as React from "react";

import {
  ContextMenuItemContent,
  ContextMenuItemDescription,
  ContextMenuItemIndicator,
  ContextMenuItemLabel,
  ContextMenuItem as ContextMenuItemElement,
  type ContextMenuItemVariant,
} from "../../elements/context-menu";
import { TickOutline } from "../../icons";

export type ContextMenuItemProps = Omit<
  BaseContextMenu.Item.Props,
  "children" | "className" | "label" | "style" | "render"
> & {
  /**
   * Row look. `neutral` is the standard text hierarchy and `danger` marks a destructive action.
   *
   * @default "neutral"
   */
  variant?: ContextMenuItemVariant;
  /** Leading element before the label, e.g. `<Icon icon={Copy} />`. */
  icon?: React.ReactNode;
  /** Primary row label. */
  label: string;
  /** Muted secondary line under the label. */
  description?: string;
  /** Content pinned at the row's inline end, e.g. `<Shortcut keys="⌘ K" />` or a count `<Badge />`. */
  trailing?: React.ReactNode;
  /**
   * Single-select selected state. Pass it on **every** `ContextMenuItem` row of a single-select
   * list (`true` or `false`) so each row reserves the trailing check gutter and its labels stay a
   * common width; omit it entirely on plain action rows, which then render no gutter.
   * `ContextMenuLinkItem` and `ContextMenuSubmenuTrigger` have no `selected` prop or gutter of
   * their own — mixing either into the same list as selected rows gives their labels more room than
   * the checked ones.
   */
  selected?: boolean;
};

/**
 * The ready-made menu row: grafts Base UI's `Item` behavior onto the styled `ContextMenuItem` and
 * composes its region parts — an optional leading icon, the label and an optional description, the
 * single-select check, and optional trailing content.
 */
export function ContextMenuItem({
  variant,
  icon,
  description,
  trailing,
  selected,
  label,
  ...props
}: ContextMenuItemProps) {
  // The taller, top-aligned row layout is implied by having a description — derived, not a prop.
  const layout = description ? "stacked" : "single";
  // See MenuItem: a row carrying `selected` is one of a mutually exclusive set, so it is exposed
  // as a radio rather than a plain command. Base UI hardcodes `role: "menuitem"` in the item's own
  // props and merges leftmost-first, so this wins — and a consumer-supplied `role` still wins over it.
  const selectionProps =
    selected === undefined ? undefined : { role: "menuitemradio", "aria-checked": selected };
  return (
    <BaseContextMenu.Item
      {...selectionProps}
      {...props}
      render={<ContextMenuItemElement layout={layout} variant={variant} />}
    >
      {icon}
      {description ? (
        <ContextMenuItemContent>
          <ContextMenuItemLabel>{label}</ContextMenuItemLabel>
          <ContextMenuItemDescription>{description}</ContextMenuItemDescription>
        </ContextMenuItemContent>
      ) : (
        <ContextMenuItemLabel>{label}</ContextMenuItemLabel>
      )}
      {/* A single-select list passes a real `selected` boolean on EVERY row; a plain action row
          passes none. Render the check gutter only for the former — and for every row, so a
          selection change never re-truncates a label (keepMounted-equivalent, like Menu). It trails
          the label rather than leading it, and sits BEFORE `trailing` so a shortcut or count keeps
          the row's outer edge. Base UI has no `ContextMenu.ItemIndicator` to set the attribute, so
          `data-selected` is set here from the boolean; `itemIndicatorClass` hides the glyph via
          `not-data-selected:invisible` without collapsing the reserved column. */}
      {selected !== undefined ? (
        <ContextMenuItemIndicator data-selected={selected ? "" : undefined}>
          <TickOutline />
        </ContextMenuItemIndicator>
      ) : null}
      {trailing}
    </BaseContextMenu.Item>
  );
}
