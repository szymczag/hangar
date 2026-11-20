import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { textAreaFieldVariants } from "./variants";

export type TextAreaFieldProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The layout frame for a text area field (label above the control). Base-UI-agnostic — graft
 * `Field.Root` in `components` via `<BaseField.Root render={<TextAreaField/>} />`.
 */
export function TextAreaField({ render, ...props }: TextAreaFieldProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: textAreaFieldVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
