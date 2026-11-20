import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  otpFieldInputVariants,
  type OTPFieldInputSize,
  type OTPFieldInputVariantProps,
} from "./variants";

export type { OTPFieldInputSize };

// `size` is omitted from the intrinsic props: the native `<input size>` (width in characters) would
// collide with the styling axis, and a styled field never sizes itself that way.
export type OTPFieldInputProps = Omit<
  useRender.ComponentProps<"input">,
  "className" | "style" | "size"
> &
  OTPFieldInputVariantProps;

/**
 * A single styled OTP character cell. Base-UI-agnostic; graft the slot behavior in `components` via
 * `<BaseOTPField.Input render={<OTPFieldInput/>} />`.
 */
export function OTPFieldInput({ size, render, ...props }: OTPFieldInputProps) {
  const defaultProps: useRender.ElementProps<"input"> = {
    className: otpFieldInputVariants({ size }),
  };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
