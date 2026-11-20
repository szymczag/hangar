import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogViewportVariants } from "./variants";

export type AlertDialogViewportProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The full-screen container: centered on desktop, bottom-aligned below 640px with 16px gutters.
 * Base-UI-agnostic — graft the viewport behavior in `components` via `<BaseAlertDialog.Viewport
 * render={<AlertDialogViewport/>} />`.
 */
export function AlertDialogViewport({ render, ...props }: AlertDialogViewportProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: alertDialogViewportVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
