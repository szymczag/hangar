import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogHeadingVariants } from "./variants";

export type DialogHeadingProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The heading block: stacks the `DialogTitle` over an optional `DialogDescription` with a tight
 * gap. Sit inside `DialogHeader` (optionally under `DialogProgression`). Keep supporting copy here
 * — not in `DialogBody` — so title/description use the 6 px heading rhythm.
 */
export function DialogHeading({ render, ...props }: DialogHeadingProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogHeadingVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
