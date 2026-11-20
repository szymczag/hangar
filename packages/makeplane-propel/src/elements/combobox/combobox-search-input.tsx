import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxSearchInputVariants } from "./variants";

export type ComboboxSearchInputProps = Omit<
  useRender.ComponentProps<"input">,
  "className" | "style"
>;

/**
 * The styled borderless text field inside `ComboboxSearch`. Base-UI-agnostic — graft the combobox
 * input behavior in `components` via `<BaseCombobox.Input render={<ComboboxSearchInput />} />`.
 */
export function ComboboxSearchInput({ render, ...props }: ComboboxSearchInputProps) {
  const defaultProps: useRender.ElementProps<"input"> = {
    className: comboboxSearchInputVariants(),
  };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
