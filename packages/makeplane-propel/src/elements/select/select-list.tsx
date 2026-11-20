import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectListVariants } from "./variants";

export type SelectListProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The list that holds the option rows, inside the popup panel's scroll area. Base-UI-agnostic —
 * graft in `components` via `<BaseSelect.List render={<SelectList />} />`.
 */
export function SelectList({ render, ...props }: SelectListProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: selectListVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
