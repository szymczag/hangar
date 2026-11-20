import { cva, cx } from "class-variance-authority";

/**
 * The shared chrome for a list row's primary interactive element — the part that fills the row and
 * makes its content area click through. `ListItemLink` (`<a>`) and `ListItemButton` (`<button>`)
 * are different elements (rule 6c) but wear identical chrome, so it lives here (rule 4). A
 * transparent `::after` covers its own box; sibling actions (disclosure, menus) sit outside that
 * box and keep their own clicks. No own outline — the wrapping `ListItem` shows the focus ring when
 * this primary is `:focus-visible` (via `[data-list-item-primary]`, stamped on the link/button
 * elements). Inherits the row's text.
 */
export const listItemPrimaryVariants = cva(
  cx(
    "relative flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-start outline-none",
    "after:absolute after:inset-0",
  ),
);

/** Attribute stamped on `ListItemLink` / `ListItemButton` so `ListItem` can ring only the primary. */
export const LIST_ITEM_PRIMARY_ATTR = "data-list-item-primary" as const;
