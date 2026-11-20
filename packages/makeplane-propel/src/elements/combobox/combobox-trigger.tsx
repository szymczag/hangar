import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ComboboxTriggerVariantProps, comboboxTriggerVariants } from "./variants";

export type {
  ComboboxTriggerAnySize,
  ComboboxTriggerPillSize,
  ComboboxTriggerVariant,
  ComboboxTriggerVariantProps,
  ComboboxTriggerWidth,
} from "./variants";

export type ComboboxTriggerProps = Omit<useRender.ComponentProps<"button">, "className" | "style"> &
  ComboboxTriggerVariantProps;

/**
 * The styled closed-field trigger button (value + chevron). Base-UI-agnostic — graft in
 * `components` via `<BaseCombobox.Trigger render={<ComboboxTrigger />} />`.
 */
export function ComboboxTrigger({ size, variant, width, render, ...props }: ComboboxTriggerProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: comboboxTriggerVariants({ size, variant, width }),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
