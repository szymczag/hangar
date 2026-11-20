import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogInfoVariants } from "./variants";

export type DialogInfoProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Optional footer helper at the inline-start of `DialogActions`. Compose a `DialogInfoIcon` and the
 * helper label as children. Flexes to push action buttons to the inline-end.
 */
export function DialogInfo({ render, ...props }: DialogInfoProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogInfoVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
