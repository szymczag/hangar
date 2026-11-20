import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ComboboxItemVariantProps, comboboxItemVariants } from "./variants";

export type { ComboboxItemVariant } from "./variants";

export type ComboboxItemProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ComboboxItemVariantProps;

/**
 * The styled option row. Base-UI-agnostic — graft the item behavior in `components` via
 * `<BaseCombobox.Item render={<ComboboxItem />} />`. Uses the shared menu-row chrome so the
 * combobox list matches the dropdown panel.
 */
export function ComboboxItem({ variant, render, ...props }: ComboboxItemProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: comboboxItemVariants({ variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
