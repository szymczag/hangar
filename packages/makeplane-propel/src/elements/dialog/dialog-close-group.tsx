import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogCloseGroupVariants } from "./variants";

export type DialogCloseGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Positions the dismiss control at the popup's top inline-end corner. Hold an `IconButton` (size
 * `xs`, variant `ghost`) with `render={<DialogClose />}` so the button chrome wins and Base UI
 * supplies close behavior.
 */
export function DialogCloseGroup({ render, ...props }: DialogCloseGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogCloseGroupVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
