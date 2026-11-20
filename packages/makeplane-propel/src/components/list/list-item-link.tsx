import type * as React from "react";

import { CompositeItem, type CompositeItemProps } from "../../base/composite";
import { ListItemCounter } from "../../elements/list/list-item-counter";
import { ListItemLabel } from "../../elements/list/list-item-label";
import { ListItemLink as ListItemLinkElement } from "../../elements/list/list-item-link";

export type ListItemLinkProps = Omit<
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
   * this link, not here.
   */
  endIcon?: React.ReactNode;
};

/**
 * A list row's primary navigation target — an `<a>` that is also a roving `Composite` item. Base
 * UI's `CompositeItem` roving behavior grafted onto the styled `elements` `ListItemLink` element
 * (rule 1a). Mark the current page with `aria-current="page"`. Pass `startIcon` for the leading
 * visual, `label` for the visible row text, `count` for a trailing count chip, and `endIcon` for a
 * trailing visual. A row's expand/collapse control (`ListItemDisclosureTrigger`) is a separate
 * sibling, never a child — a button can't nest inside this `<a>`.
 */
export function ListItemLink({ startIcon, label, count, endIcon, ...props }: ListItemLinkProps) {
  // Hide the chip for `0` / empty — callers pass live unread totals; use a non-zero node (or
  // `"0"`) when a zero chip must stay visible.
  const showCount = count != null && count !== 0 && count !== "";
  return (
    <CompositeItem tag="a" {...props} render={<ListItemLinkElement />}>
      {startIcon}
      <ListItemLabel>{label}</ListItemLabel>
      {showCount ? <ListItemCounter>{count}</ListItemCounter> : null}
      {endIcon}
    </CompositeItem>
  );
}
