import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogTitleVariants } from "./variants";

export type DialogTitleProps = Omit<useRender.ComponentProps<"h2">, "className" | "style">;

/**
 * Styled dialog title chrome (`text-h5-medium`). Base-UI-agnostic — graft title behavior in
 * `components` via `<BaseDialog.Title render={<DialogTitle />} />`. Dialog-owned (diverges from
 * shared `OverlayTitle`).
 */
export function DialogTitle({ render, ...props }: DialogTitleProps) {
  const defaultProps: useRender.ElementProps<"h2"> = { className: dialogTitleVariants() };
  return useRender({ defaultTagName: "h2", render, props: mergeProps(defaultProps, props) });
}
