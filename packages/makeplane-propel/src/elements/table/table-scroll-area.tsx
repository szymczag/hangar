import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TableScrollAreaVariantProps, tableScrollAreaVariants } from "./variants";

export type TableScrollAreaProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  TableScrollAreaVariantProps;

/**
 * The scroll frame around a `Table` — a single styled `<div>`, rounded and hairline-bordered for
 * the framed looks and bare for `variant="plain"`. It bakes no scroll behavior: Base-UI-agnostic —
 * the ready-made `components/table` grafts the Base UI `ScrollArea.Root` onto it via
 * `<BaseScrollArea.Root render={<TableScrollArea/>} />` (behavior part outer), alongside the
 * `TableScrollAreaViewport`, the `<table>`, and the scrollbars.
 */
export function TableScrollArea({ variant, render, ...props }: TableScrollAreaProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: tableScrollAreaVariants({ variant }) }, props),
  });
}
