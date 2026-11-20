import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type RadioGroupOptionsVariantProps, radioGroupOptionsVariants } from "./variants";

export type { RadioGroupOptionsOrientation } from "./variants";

export type RadioGroupOptionsProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  RadioGroupOptionsVariantProps;

/**
 * The layout wrapper around a radio group's option rows. It keeps option orientation independent
 * from the fieldset's legend and supporting text.
 */
export function RadioGroupOptions({
  density,
  orientation,
  render,
  ...props
}: RadioGroupOptionsProps) {
  const defaultProps: useRender.ElementProps<"div"> & { "data-slot": string } = {
    className: radioGroupOptionsVariants({ density, orientation }),
    "data-slot": "radio-group-options",
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
