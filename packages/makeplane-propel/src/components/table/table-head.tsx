import * as React from "react";

import {
  TableHead as TableHeadElement,
  type TableHeadProps as TableHeadElementProps,
  TableHeadSortIndicator,
  TableHeadSortTrigger,
  TableHeadTitle,
} from "../../elements/table/index";
import { ChevronDownOutline, ChevronExpandOutline, ChevronUpOutline } from "../../icons";
export type { TableAlign, TableHeadInset } from "../../elements/table/index";
import { useTableVariant } from "./table-context";

/** Sort direction of a sortable `TableHead`. `none` shows the neutral affordance. */
export type TableHeadSort = "asc" | "desc" | "none";

const sortGlyph: Record<TableHeadSort, typeof ChevronExpandOutline> = {
  asc: ChevronUpOutline,
  desc: ChevronDownOutline,
  none: ChevronExpandOutline,
};

/** Only active directions expose `aria-sort` (APG); unsorted sortable headers omit the attribute. */
const ariaSort: Partial<Record<TableHeadSort, React.AriaAttributes["aria-sort"]>> = {
  asc: "ascending",
  desc: "descending",
};

export type TableHeadProps = Omit<TableHeadElementProps, "aria-sort" | "variant" | "children"> & {
  /**
   * Header label. Rendered in a truncating title region.
   *
   * Omit it only when `children` supplies the header's own content — a sort/filter menu, a
   * select-all checkbox, a tooltip trigger. Pass `label` as well in that case if the content has no
   * accessible text of its own: `children` replace the title region, so the label is kept as
   * screen-reader-only text beside them rather than shown.
   */
  label?: string;
  /**
   * Header content, when a plain label is not enough. Replaces the title region; a sortable header
   * still wraps it in the sort control. The cell's own chrome — background, borders, padding,
   * stickiness, alignment — is unaffected.
   */
  children?: React.ReactNode;
  /**
   * Visually hide the label while keeping it available to assistive tech.
   *
   * @default false
   */
  visuallyHidden?: boolean;
  /**
   * Enable sorting on this header. Renders a sort trigger when `onSort` is also provided. Sets
   * `aria-sort` for `asc` / `desc` only (omitted while unsorted).
   *
   * @default false
   */
  sortable?: boolean;
  /** Current sort state for a sortable header. @default "none" */
  sort?: TableHeadSort;
  /**
   * Click handler for the sort control; required (with `sortable`) for the header to be
   * interactive.
   */
  onSort?: () => void;
} & ({ label: string } | { children: Exclude<React.ReactNode, null | undefined | boolean> });

/**
 * A ready-made header cell: a plain title, arbitrary `children`, or (when sortable) either of those
 * inside a sort-cycling button with a chevron.
 */
export function TableHead({
  label,
  children,
  visuallyHidden = false,
  sortable = false,
  sort = "none",
  onSort,
  ...props
}: TableHeadProps) {
  const tableVariant = useTableVariant();
  const hasSortControl = sortable && onSort != null;
  const SortGlyph = sortGlyph[sort];
  const titleVisibility = visuallyHidden ? "hidden" : "visible";
  // `children` replace the title region, so a `label` passed alongside them has nowhere to render.
  // Keep it as screen-reader text rather than dropping it: an icon-only header given
  // `label="Settings"` was otherwise left with no accessible name at all, which is the fallback this
  // prop documents. It is text and not an `aria-label` because axe's `empty-table-header` wants a
  // header to have text in the accessibility tree — a label override on the `<th>` fails that rule.
  const content =
    children != null ? (
      <>
        {label != null ? <TableHeadTitle visibility="hidden">{label}</TableHeadTitle> : null}
        {children}
      </>
    ) : (
      <TableHeadTitle visibility={titleVisibility}>{label}</TableHeadTitle>
    );

  return (
    <TableHeadElement
      variant={tableVariant}
      aria-sort={hasSortControl ? ariaSort[sort] : undefined}
      {...props}
    >
      {hasSortControl ? (
        <TableHeadSortTrigger onClick={onSort}>
          {content}
          <TableHeadSortIndicator>
            <SortGlyph />
          </TableHeadSortIndicator>
        </TableHeadSortTrigger>
      ) : (
        content
      )}
    </TableHeadElement>
  );
}
