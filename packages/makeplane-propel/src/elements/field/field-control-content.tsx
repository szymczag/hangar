import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type FieldControlContentVariantProps, fieldControlContentVariants } from "./variants";

export type FieldControlContentProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  FieldControlContentVariantProps;

/** The control + helper-text column shared by `InputField` and `TextAreaField`. */
export function FieldControlContent({
  orientation,
  size,
  render,
  ...props
}: FieldControlContentProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: fieldControlContentVariants({ orientation, size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
