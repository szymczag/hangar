import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogActionGroupVariants } from "./variants";

export type AlertDialogActionGroupProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
>;

/** Keeps related footer actions together in a split footer. */
export function AlertDialogActionGroup({ render, ...props }: AlertDialogActionGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: alertDialogActionGroupVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
