import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type NumberFieldInputVariantProps, numberFieldInputVariants } from "./variants";

export type { NumberFieldSize, NumberFieldStepperSize } from "./variants";
export { numberFieldStepperSize } from "./variants";

// Styling `size` is omitted from the intrinsic props: the native `<input size>` (width in
// characters) would collide with that axis. The native attribute is still set below as a private
// default so browsers without `field-sizing: content` don't fall back to the ~20ch intrinsic width.
export type NumberFieldInputProps = Omit<
  useRender.ComponentProps<"input">,
  "className" | "style" | "size"
> &
  NumberFieldInputVariantProps;

/**
 * The styled numeric input. Base-UI-agnostic — graft the number field behavior in `components` via
 * `<BaseNumberField.Input render={<NumberFieldInput/>} />`.
 *
 * @param size Visual size of the value cell (type + min-width). Match the wrapping group's `size`.
 */
export function NumberFieldInput({ size, render, ...props }: NumberFieldInputProps) {
  const defaultProps: useRender.ElementProps<"input"> = {
    className: numberFieldInputVariants({ size }),
    // Fallback intrinsic width (ch) when `field-sizing-content` is unsupported (Safari < 26.2,
    // Firefox < 152). Not part of the public API — styling axis owns the name `size`.
    size: 4,
  };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
