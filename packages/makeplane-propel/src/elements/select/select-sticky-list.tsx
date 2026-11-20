import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectStickyListVariants } from "./variants";

export type SelectStickyListProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Pads sticky rows in the panel header (a Select all row + separator) with the same inset the
 * scrolling list uses, so they line up with the options below.
 */
export function SelectStickyList({ render, ...props }: SelectStickyListProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: selectStickyListVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
