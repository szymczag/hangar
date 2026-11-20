import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { textButtonLabelVariants } from "./variants";

export type TextButtonLabelProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/** The visible, unadorned label inside a `TextButton`. */
export function TextButtonLabel({ render, ...props }: TextButtonLabelProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: textButtonLabelVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
