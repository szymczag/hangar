import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ComboboxInputGroupVariantProps, comboboxInputGroupVariants } from "./variants";

export type { ComboboxSize, ComboboxVariant } from "./variants";

export type ComboboxInputGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ComboboxInputGroupVariantProps;

/**
 * The styled frame around the input + its adornments. Base-UI-agnostic — graft in `components` via
 * `<BaseCombobox.InputGroup render={<ComboboxInputGroup/>} />`.
 */
export function ComboboxInputGroup({ size, variant, render, ...props }: ComboboxInputGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: comboboxInputGroupVariants({ size, variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
