import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogTitleVariants } from "./variants";

export type AlertDialogTitleProps = Omit<useRender.ComponentProps<"h2">, "className" | "style">;

/**
 * The alert dialog heading. Base-UI-agnostic — graft the title behavior in `components` via
 * `<BaseAlertDialog.Title render={<AlertDialogTitle />} />`.
 */
export function AlertDialogTitle({ render, ...props }: AlertDialogTitleProps) {
  const defaultProps: useRender.ElementProps<"h2"> = { className: alertDialogTitleVariants() };
  return useRender({ defaultTagName: "h2", render, props: mergeProps(defaultProps, props) });
}
