import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { inputVariants, type InputSize, type InputVariantProps } from "./variants";

export type { InputSize };

// `size` is omitted from the intrinsic props: the native `<input size>` (width in characters) would
// collide with the styling axis, and a styled field never sizes itself that way.
export type InputProps = Omit<useRender.ComponentProps<"input">, "className" | "style" | "size"> &
  InputVariantProps;

/**
 * The styled single-line text field. Base-UI-agnostic — graft the Base UI `Input` control behavior
 * in `components` via `<BaseInput render={<Input/>} />`.
 */
export function Input({ size, render, ...props }: InputProps) {
  const defaultProps: useRender.ElementProps<"input"> = {
    className: inputVariants({ size }),
  };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
