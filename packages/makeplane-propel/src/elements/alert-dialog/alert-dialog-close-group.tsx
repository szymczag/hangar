import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogCloseGroupVariants } from "./variants";

export type AlertDialogCloseGroupProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
>;

/**
 * Positions the corner dismiss control at the popup's top-end. Pass an `IconButton` (components
 * tier) or the styled `AlertDialogClose` (elements showcase) as the child.
 */
export function AlertDialogCloseGroup({ render, ...props }: AlertDialogCloseGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: alertDialogCloseGroupVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
