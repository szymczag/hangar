import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type FieldVariantProps, fieldVariants } from "./variants";

export type FieldProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  FieldVariantProps;

/**
 * The shared field chrome for custom controls. Base-UI-agnostic — graft the Base UI field
 * labeling/validation behavior in `components` via `<BaseField.Root render={<Field/>} />`. Compose
 * it with `FieldLabel`, a control, `FieldDescription`, and `FieldError`.
 */
export function Field({ size, render, ...props }: FieldProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: fieldVariants({ size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
