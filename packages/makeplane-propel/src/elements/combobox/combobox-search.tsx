import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxSearchVariants } from "./variants";

export type ComboboxSearchProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** The sticky search row pinned above a combobox popup list (a search icon + `ComboboxSearchInput`). */
export function ComboboxSearch({ render, ...props }: ComboboxSearchProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: comboboxSearchVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
