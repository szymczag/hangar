import * as React from "react";

import { TableRow } from "./table-row";
import { TableShowMoreCell } from "./table-show-more-cell";

export type TableNestedRowsProps<Item> = {
  /** The nested rows' data, in display order. */
  items: readonly Item[];
  /** A stable key for an item. */
  getKey: (item: Item, index: number) => React.Key;
  /**
   * Renders one nested row: a `TableRow` whose first cell is a `TableExpandCell`. The third
   * argument carries this group's `depth`; pass it to that cell so the rows and the "show more"
   * button are indented from one value.
   */
  renderRow: (item: Item, index: number, group: { depth: number }) => React.ReactNode;
  /** How many columns the table has, so the "show more" row spans all of them. */
  colSpan: number;
  /** The "show more" button's text, given how many rows are still hidden, e.g. `"Show 16 more"`. */
  showMoreLabel: (hidden: number) => string;
  /**
   * How many rows to show before the "show more" row. A group with this many rows or fewer shows
   * them all and no button.
   *
   * @default 5
   */
  maxVisible?: number;
  /**
   * Nesting level of these rows. It indents the "show more" button and is handed to `renderRow` for
   * the rows themselves.
   *
   * @default 1
   */
  depth?: number;
};

/**
 * The nested rows under an expanded parent, with the "show more" behaviour built in. It renders the
 * first `maxVisible` rows and, while any are hidden, a `TableShowMoreCell` row that reveals the
 * rest. Render it after the parent `TableRow` while the parent is expanded:
 *
 * ```tsx
 * {expanded ? <TableNestedRows items={page.children} … /> : null}
 * ```
 *
 * It renders rows only, with no wrapper element, so it sits directly in a `TableBody`. Revealing
 * the rest removes the button, so focus moves to the first row it revealed instead of being lost.
 * Collapsing the parent unmounts the group, so it opens on its first `maxVisible` rows again.
 *
 * It is optional. For anything it does not cover — paging nested rows from a server, revealing a
 * page at a time — compose `TableRow`, `TableExpandCell` and `TableShowMoreCell` directly.
 */
export function TableNestedRows<Item>({
  items,
  getKey,
  renderRow,
  colSpan,
  showMoreLabel,
  maxVisible = 5,
  depth = 1,
}: TableNestedRowsProps<Item>) {
  const [showAll, setShowAll] = React.useState(false);
  // The last row on screen when "show more" was activated; the first revealed row follows it.
  const lastVisibleRow = React.useRef<Element | null>(null);

  React.useEffect(() => {
    const revealed = lastVisibleRow.current?.nextElementSibling;
    lastVisibleRow.current = null;
    if (!(revealed instanceof HTMLElement)) return;
    // A row is not focusable by default. `-1` lets it take this programmatic focus without joining
    // the tab order, so the next Tab goes to the row's own controls. React does not know about the
    // attribute, so it is taken off again when focus leaves; otherwise the row would stay focusable
    // and a later click anywhere on it would focus the `<tr>`.
    revealed.tabIndex = -1;
    revealed.addEventListener("blur", () => revealed.removeAttribute("tabindex"), { once: true });
    revealed.focus();
  }, [showAll]);

  const visible = showAll ? items : items.slice(0, maxVisible);
  const hidden = items.length - visible.length;

  return (
    <>
      {visible.map((item, index) => (
        <React.Fragment key={getKey(item, index)}>
          {renderRow(item, index, { depth })}
        </React.Fragment>
      ))}
      {hidden > 0 ? (
        <TableRow>
          <TableShowMoreCell
            colSpan={colSpan}
            depth={depth}
            label={showMoreLabel(hidden)}
            onClick={(event) => {
              lastVisibleRow.current =
                event.currentTarget.closest("tr")?.previousElementSibling ?? null;
              setShowAll(true);
            }}
          />
        </TableRow>
      ) : null}
    </>
  );
}
