import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type SelectLabelVariantProps, selectLabelVariants } from "./variants";

export type { SelectLabelSize } from "./variants";

export type SelectLabelProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  SelectLabelVariantProps;

/**
 * The styled select label. Base-UI-agnostic — graft the label behavior in `components` via
 * `<BaseSelect.Label render={<SelectLabel/>} />`.
 */
export function SelectLabel({ render, size, ...props }: SelectLabelProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: selectLabelVariants({ size }) };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
