import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { tableVariants } from "./variants";

export type { TableAlign, TablePinned, TableVariant } from "./variants";

export type TableProps = Omit<useRender.ComponentProps<"table">, "className" | "style">;

/**
 * The styled `<table>` element — a single element. The ready-made `components/table` wraps it in
 * the scroll frame (`TableScrollArea` + `TableScrollAreaViewport`, rounded and bordered except in
 * the `plain` look) and shares the layout `variant` with the rows/cells/heads via context.
 */
export function Table({ render, ...props }: TableProps) {
  const defaultProps: useRender.ElementProps<"table"> = { className: tableVariants() };
  return useRender({ defaultTagName: "table", render, props: mergeProps(defaultProps, props) });
}
