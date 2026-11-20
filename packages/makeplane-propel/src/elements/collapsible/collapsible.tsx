import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { collapsibleVariants } from "./variants";

export type CollapsibleProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The styled collapsible frame (`w-full`). Base-UI-agnostic — graft the collapsible behavior in
 * `components` via `<BaseCollapsible.Root render={<Collapsible />} />`.
 */
export function Collapsible({ render, ...props }: CollapsibleProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: collapsibleVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
