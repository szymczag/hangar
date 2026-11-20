import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxValueVariants } from "./variants";

export type ComboboxValueProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The selected-value (or placeholder) label inside `ComboboxTrigger`. Base-UI-agnostic — wrap
 * `<BaseCombobox.Value />` with this span in `components`.
 */
export function ComboboxValue({ render, ...props }: ComboboxValueProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: comboboxValueVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
