import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogViewportVariants } from "./variants";

export type DialogViewportProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The full-screen container that anchors the popup 80 px from the top edge, with the same margin
 * below once the popup reaches its ceiling. Base-UI-agnostic — graft the dialog behavior in
 * `components` via `<BaseDialog.Viewport render={<DialogViewport />} />`.
 */
export function DialogViewport({ render, ...props }: DialogViewportProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogViewportVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
