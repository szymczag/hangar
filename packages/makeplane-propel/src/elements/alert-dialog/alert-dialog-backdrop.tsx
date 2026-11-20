import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogBackdropVariants } from "./variants";

export type AlertDialogBackdropProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** Dims the viewport with the updated Figma 25% black scrim. */
export function AlertDialogBackdrop({ render, ...props }: AlertDialogBackdropProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: alertDialogBackdropVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
