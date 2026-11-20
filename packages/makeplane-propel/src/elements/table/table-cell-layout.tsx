import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import type * as React from "react";

import { tableCellLayoutVariants } from "./variants";

export type TableCellLayoutProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> & {
  /**
   * Nesting level of the row this cell belongs to. `0` is a top-level row; each level indents the
   * content by 24px, so a nested row reads as a child of the row above it.
   *
   * @default 0
   */
  depth?: number;
};

/**
 * The inline layout inside a plain `TableCell`: a leading node slot, a growing `TableCellContent`,
 * and a trailing node slot (the shared internal `NodeSlot`). Sets the slot `--node-size`. `depth`
 * indents it for a nested row.
 */
export function TableCellLayout({ depth = 0, render, ...props }: TableCellLayoutProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: tableCellLayoutVariants(),
    // The indent is a length the cva multiplies out, so it travels as a custom property.
    style: depth > 0 ? ({ "--table-depth": depth } as React.CSSProperties) : undefined,
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
