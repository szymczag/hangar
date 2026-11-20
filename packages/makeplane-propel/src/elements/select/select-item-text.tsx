import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectItemTextVariants } from "./variants";

export type SelectItemTextProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * An option's label, inside the row's `SelectItemTitleRow`. Truncates rather than wrapping.
 * Base-UI-agnostic — graft in `components` via `<BaseSelect.ItemText render={<SelectItemText />}
 * />`.
 */
export function SelectItemText({ render, ...props }: SelectItemTextProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: selectItemTextVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
