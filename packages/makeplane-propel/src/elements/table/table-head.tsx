import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TableHeadVariantProps, tableHeadVariants } from "./variants";

export type { TableHeadInset } from "./variants";

// `align` is omitted deliberately: the deprecated native attribute would intersect with — and
// collapse — the `align` styling axis this part exposes instead.
export type TableHeadProps = Omit<useRender.ComponentProps<"th">, "className" | "style" | "align"> &
  TableHeadVariantProps;

/**
 * A header cell (`<th scope="col">`). Borders follow the `variant`. Holds a `TableHeadTitle` (or,
 * when sortable, a `TableHeadSortTrigger`).
 */
export function TableHead({ variant, pinned, align, inset, render, ...props }: TableHeadProps) {
  const defaultProps: useRender.ElementProps<"th"> = {
    scope: "col",
    className: tableHeadVariants({ variant, pinned, align, inset }),
  };
  return useRender({ defaultTagName: "th", render, props: mergeProps(defaultProps, props) });
}
