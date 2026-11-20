import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TableCellVariantProps, tableCellVariants } from "./variants";

export type { TableCellPadding } from "./variants";

// `align` is omitted deliberately: the deprecated native attribute would intersect with — and
// collapse — the `align` styling axis the ready-made cell exposes.
export type TableCellProps = Omit<useRender.ComponentProps<"td">, "className" | "style" | "align"> &
  TableCellVariantProps;

/** A data cell (`<td>`). Borders follow the `variant`. */
export function TableCell({ variant, pinned, padding, render, ...props }: TableCellProps) {
  const defaultProps: useRender.ElementProps<"td"> = {
    className: tableCellVariants({ variant, pinned, padding }),
  };
  return useRender({ defaultTagName: "td", render, props: mergeProps(defaultProps, props) });
}
