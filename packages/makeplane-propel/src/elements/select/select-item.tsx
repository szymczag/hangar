import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type SelectItemVariantProps, selectItemVariants } from "./variants";

export type { SelectItemLayout } from "./variants";

export type SelectItemProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  SelectItemVariantProps;

/**
 * The styled option row. Base-UI-agnostic — graft the item behavior in `components` via
 * `<BaseSelect.Item render={<SelectItem />} />`. Uses the shared menu-row chrome so the select list
 * matches the Combobox and Menu panels. Lays its children out as a flex row: an optional leading
 * checkbox and icon, the `SelectItemContent` text column, the trailing `SelectItemIndicator`, then
 * any `SelectItemTrailing`.
 */
export function SelectItem({ layout, render, ...props }: SelectItemProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: selectItemVariants({ layout }) };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
