import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type NumberFieldGroupVariantProps, numberFieldGroupVariants } from "./variants";

export type { NumberFieldSize } from "./variants";

export type NumberFieldGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  NumberFieldGroupVariantProps;

/**
 * The styled bordered group wrapping the decrement / input / increment controls. Base-UI-agnostic —
 * graft in `components` via `<BaseNumberField.Group render={<NumberFieldGroup/>} />`.
 *
 * @param size Visual size of the frame. Matches the field's outer height (`sm` 24 / `md` 28 / `lg`
 *   32). Pair steppers with `numberFieldStepperSize[size]`.
 */
export function NumberFieldGroup({ size, render, ...props }: NumberFieldGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: numberFieldGroupVariants({ size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
