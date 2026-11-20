import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogInfoIconVariants } from "./variants";

export type DialogInfoIconProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * Decorative 14 px icon slot inside `DialogInfo`. Bakes `aria-hidden` and sizes its child via the
 * shared node-slot. Pass a Propel glyph (or `<Icon icon={…} />`) as children.
 */
export function DialogInfoIcon({ render, ...props }: DialogInfoIconProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: dialogInfoIconVariants(),
    "aria-hidden": true,
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
