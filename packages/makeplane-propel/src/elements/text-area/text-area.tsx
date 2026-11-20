import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type TextAreaSize,
  type TextAreaSurface,
  type TextAreaVariantProps,
  textAreaVariants,
} from "./variants";

export type { TextAreaSize, TextAreaSurface };

export type TextAreaProps = Omit<useRender.ComponentProps<"textarea">, "className" | "style"> &
  TextAreaVariantProps;

/**
 * The styled multi-line textarea leaf. Base-UI-agnostic — graft the Base UI `Field.Control`
 * behavior in `components` via `<BaseField.Control render={<TextArea/>} />`. Compose the `field`
 * surface inside a `TextAreaGroup` frame (the group owns `resize`). Pair `autoResize` with
 * `resize="none"` on that frame so the native drag handle does not fight content-driven height.
 */
export function TextArea({ size, surface, autoResize = false, render, ...props }: TextAreaProps) {
  const defaultProps: useRender.ElementProps<"textarea"> = {
    className: textAreaVariants({ size, surface, autoResize }),
    ...(autoResize ? { "data-auto-resize": "" } : null),
  };
  return useRender({ defaultTagName: "textarea", render, props: mergeProps(defaultProps, props) });
}
