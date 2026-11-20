import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TableRowVariantProps, tableRowVariants } from "./variants";

export type TableRowProps = Omit<useRender.ComponentProps<"tr">, "className" | "style"> &
  TableRowVariantProps;

/**
 * A table row (`<tr>`). `variant` is the surrounding table look, which decides the resting row
 * fill. `selected` paints Figma's selected tint and exposes `data-selected` so a pinned cell in
 * this row can follow it; `interactive` marks the row as a click target.
 *
 * `selected` is a visual state only. Pair it with a `TableSelectCell`, whose checkbox carries the
 * real state: a checkbox announces itself, and `aria-multiselectable` is not valid on a plain
 * `table`, so a bare `aria-selected` on the row says less and is easier to leave out of sync.
 */
export function TableRow({
  variant,
  selected,
  interactive,
  section,
  render,
  ...props
}: TableRowProps) {
  const defaultProps: useRender.ElementProps<"tr"> = {
    className: tableRowVariants({ variant, selected, interactive, section }),
    ...(selected ? { "data-selected": "" } : {}),
    ...(section ? { "data-section": "" } : {}),
  };
  return useRender({ defaultTagName: "tr", render, props: mergeProps(defaultProps, props) });
}
