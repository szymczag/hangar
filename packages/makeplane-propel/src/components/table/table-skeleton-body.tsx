import type * as React from "react";

import {
  TableSkeletonBody as TableSkeletonBodyElement,
  type TableSkeletonBodyProps as TableSkeletonBodyElementProps,
} from "../../elements/table/index";
import { TableRow } from "./table-row";

export type TableSkeletonBodyProps = Omit<
  TableSkeletonBodyElementProps,
  "children" | "aria-busy" | "aria-label"
> & {
  /**
   * ONE row's worth of `TableSkeletonCell`s. They are redrawn for each row, so the skeleton takes
   * its column count from the same `<thead>` the loaded table uses — no count to pass, and nothing
   * to keep in sync when a column is added.
   */
  children: React.ReactNode;
  /**
   * How many placeholder rows to draw.
   *
   * @default 5
   */
  rows?: number;
  /**
   * Accessible name for the loading region, e.g. `"Loading members"`. Required — the bars are
   * `aria-hidden`, so without it the wait is announced as nothing at all.
   */
  "aria-label": string;
};

/**
 * The loading `<tbody>`: takes one row of cells and repeats it, inside a pulsing, non-interactive
 * body marked `role="status"` and `aria-busy`.
 *
 * Swap it for `TableBody` once the data arrives. What carries over is the table's structure — the
 * same `<thead>`, the same cell chrome, the same 44px row — so the placeholder reads as the table
 * it stands in for rather than as a generic block.
 *
 * It does NOT freeze the column widths. A `<table>` lays out automatically by default, so the
 * columns are sized by whatever is in them, and swapping bars for text re-sizes them: in a 800px
 * example an email column measured 272px under the skeleton and 498px once loaded. A consumer that
 * needs the columns to hold still has to take the layout out of the content's hands —
 * `render={<table className="table-fixed" />}` on `Table`, with widths on the headers.
 */
export function TableSkeletonBody({ children, rows = 5, ...props }: TableSkeletonBodyProps) {
  return (
    <TableSkeletonBodyElement role="status" aria-busy {...props}>
      {Array.from({ length: rows }, (_unused, index) => (
        <TableRow key={index}>{children}</TableRow>
      ))}
    </TableSkeletonBodyElement>
  );
}
