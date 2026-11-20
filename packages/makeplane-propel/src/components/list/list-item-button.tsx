import type * as React from "react";

import { CompositeItem, type CompositeItemProps } from "../../base/composite";
import { ListItemButton as ListItemButtonElement } from "../../elements/list/list-item-button";
import { ListItemCounter } from "../../elements/list/list-item-counter";
import { ListItemLabel } from "../../elements/list/list-item-label";

export type ListItemButtonProps = Omit<
  CompositeItemProps,
  "children" | "className" | "style" | "tag" | "render"
> & {
  /** Element rendered before the label, usually `<Icon icon={...} />`. */
  startIcon?: React.ReactNode;
  /** Visible row label. */
  label: string;
  /**
   * Trailing count chip, e.g. an unread total. `0` and `""` are omitted (no empty/zero chip); pass
   * a non-empty node (or the string `"0"`) when a zero must stay visible.
   */
  count?: React.ReactNode;
  /**
   * Trailing visual after the count, usually `<Icon icon={...} />`. Part of the primary hit target
   * — not a separate control. Put interactive trailing actions (disclosure, menus) as siblings of
   * this button, not here.
   */
  endIcon?: React.ReactNode;
};

/**
 * A list row's primary action — a `<button>` that is also a roving `Composite` item. Base UI's
 * `CompositeItem` roving behavior grafted onto the styled `elements` `ListItemButton` element (rule
 * 1a). Pass `startIcon` for the leading visual, `label` for the visible row text, `count` for a
 * trailing count chip, and `endIcon` for a trailing visual. A row's expand/collapse control
 * (`ListItemDisclosureTrigger`) is a separate sibling, never a child — a button can't nest inside
 * this `<button>`.
 */
export function ListItemButton({
  startIcon,
  label,
  count,
  endIcon,
  ...props
}: ListItemButtonProps) {
  // Hide the chip for `0` / empty — callers pass live unread totals; use a non-zero node (or
  // `"0"`) when a zero chip must stay visible.
  const showCount = count != null && count !== 0 && count !== "";
  return (
    <CompositeItem tag="button" {...props} render={<ListItemButtonElement />}>
      {startIcon}
      <ListItemLabel>{label}</ListItemLabel>
      {showCount ? <ListItemCounter>{count}</ListItemCounter> : null}
      {endIcon}
    </CompositeItem>
  );
}
