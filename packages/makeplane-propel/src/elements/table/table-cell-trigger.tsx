import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TableCellTriggerVariantProps, tableCellTriggerVariants } from "./variants";

export type { TableCellTriggerLayout } from "./variants";

export type TableCellTriggerProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style" | "type"
> &
  TableCellTriggerVariantProps;

/**
 * The full-cell `<button>` inside an editable/action cell — a single styled element. Base-UI-
 * agnostic: the ready-made `components/table` grafts the Base UI Menu trigger onto it via `render`
 * (`<BaseMenu.Trigger render={<TableCellTrigger/>} />`, behavior part outer). Carries a
 * `cell-trigger` group so its indicator can dim while disabled.
 *
 * `selected` is a visual tint only (open-menu / active chrome) — not an ARIA selected state.
 *
 * @default false
 */
export function TableCellTrigger({ layout, selected, render, ...props }: TableCellTriggerProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    type: "button",
    className: tableCellTriggerVariants({ layout, selected }),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
