import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectFooterVariants } from "./variants";

export type SelectFooterProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** A non-interactive footer pinned below the list, passed through `SelectContent`'s `footer`. */
export function SelectFooter({ render, ...props }: SelectFooterProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: selectFooterVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
