import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxStickyListVariants } from "./variants";

export type ComboboxStickyListProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The padded inset around sticky rows in the overlay header (Select all + separator). Matches the
 * flat popup's `p-1` so header rows align with the scrolling list.
 */
export function ComboboxStickyList({ render, ...props }: ComboboxStickyListProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: comboboxStickyListVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
