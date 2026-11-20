import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { fieldItemVariants } from "./variants";

export type FieldItemProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Groups one checkbox or radio option with its label and optional description. Base-UI-agnostic —
 * graft the Base UI `Field.Item` behavior in `components` via `<BaseField.Item
 * render={<FieldItem/>} />`.
 */
export function FieldItem({ render, ...props }: FieldItemProps) {
  // `data-slot` is a stable test/composition hook (avoid keying off utility classes). Intersected
  // onto ElementProps because this repo's React DOM typings don't admit arbitrary `data-*` keys on
  // the annotated defaultProps object even though the attribute is valid at runtime.
  const defaultProps: useRender.ElementProps<"div"> & { "data-slot": string } = {
    className: fieldItemVariants(),
    "data-slot": "field-item",
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
