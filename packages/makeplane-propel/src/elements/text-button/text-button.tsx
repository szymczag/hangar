import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type TextButtonVariantProps, textButtonVariants } from "./variants";

export type { TextButtonSize, TextButtonVariant } from "./variants";

export type TextButtonProps = Omit<useRender.ComponentProps<"button">, "className" | "style"> &
  TextButtonVariantProps;

/**
 * The styled intrinsic button for low-emphasis actions with a lightweight text-only look. Selects
 * the action palette (`variant`) and text size (`size`). Base-UI-agnostic — graft Base UI's Button
 * behavior in `components`. Does not accept `className` or `style`.
 */
export function TextButton({ variant, size, render, ...props }: TextButtonProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: textButtonVariants({ variant, size }),
  };
  return useRender({
    defaultTagName: "button",
    render,
    state: { variant, size },
    props: mergeProps(defaultProps, props),
  });
}
