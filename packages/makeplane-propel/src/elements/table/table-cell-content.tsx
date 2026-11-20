import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TableCellContentVariantProps, tableCellContentVariants } from "./variants";

export type TableCellContentProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  TableCellContentVariantProps;

/**
 * The growing text region inside a `TableCellLayout`. Truncates instead of overflowing, and carries
 * the column's `align` — the cell's layout is a flex row, so `text-align` has to land here.
 */
export function TableCellContent({ align, render, ...props }: TableCellContentProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: tableCellContentVariants({ align }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
