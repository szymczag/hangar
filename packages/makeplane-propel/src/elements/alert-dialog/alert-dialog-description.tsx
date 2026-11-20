import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogDescriptionVariants } from "./variants";

export type AlertDialogDescriptionProps = Omit<
  useRender.ComponentProps<"p">,
  "className" | "style"
>;

/**
 * Supporting copy under the alert dialog title. Base-UI-agnostic — graft the description behavior
 * in `components` via `<BaseAlertDialog.Description render={<AlertDialogDescription />} />`.
 */
export function AlertDialogDescription({ render, ...props }: AlertDialogDescriptionProps) {
  const defaultProps: useRender.ElementProps<"p"> = {
    className: alertDialogDescriptionVariants(),
  };
  return useRender({ defaultTagName: "p", render, props: mergeProps(defaultProps, props) });
}
