import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { tableSelectLayoutVariants } from "./variants";

export type TableSelectLayoutProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Centres a selection checkbox inside an unpadded cell or header, filling it so the whole 44px box
 * is the pointer target.
 */
export function TableSelectLayout({ render, ...props }: TableSelectLayoutProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: tableSelectLayoutVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
