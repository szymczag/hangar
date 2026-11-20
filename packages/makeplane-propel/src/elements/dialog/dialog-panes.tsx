import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogPanesVariants } from "./variants";

export type DialogPanesProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The side-by-side row of a two-pane dialog: `DialogAside` on the start side, `DialogMain` filling
 * the rest. Sits between optional `DialogToolbar` and `DialogActions` in the popup, at any `size`.
 * Fills the popup's height when the popup pins it (`size="full"` or `height="fixed"`).
 */
export function DialogPanes({ render, ...props }: DialogPanesProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogPanesVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
