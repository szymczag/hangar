import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { toolbarGroupVariants } from "./variants";

export type ToolbarGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * A cluster of related controls. Per Figma it carries the SAME `gap-2` as the toolbar row, so it
 * packs nothing more tightly than bare children — grouping reads from the separators either side,
 * and this part exists for the semantics (`role="group"` + group `disabled`) rather than the
 * spacing. Base-UI-agnostic: graft the group behavior in `components` via `<BaseToolbar.Group
 * render={<ToolbarGroup/>} />`.
 */
export function ToolbarGroup({ render, ...props }: ToolbarGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: toolbarGroupVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
