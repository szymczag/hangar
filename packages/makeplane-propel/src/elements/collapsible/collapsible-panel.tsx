import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { collapsiblePanelVariants } from "./variants";

export type CollapsiblePanelProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The height-animating collapsible panel (geometry + open/close transition only). Body prose and
 * padding live on `CollapsiblePanelContent`. Base-UI-agnostic — graft in `components` via
 * `<BaseCollapsible.Panel render={<CollapsiblePanel/>} />`.
 */
export function CollapsiblePanel({ render, ...props }: CollapsiblePanelProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: collapsiblePanelVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
