import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogHeaderVariants } from "./variants";

export type DialogHeaderProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The top block inside `DialogMain`: stacks an optional `DialogProgression` over a `DialogHeading`
 * (title + optional description). Dismiss lives in `DialogCloseGroup` on the popup, not here — this
 * part carries extra end padding so progression/title clear the absolute close without widening
 * Main/Body gutters. Full-width header controls (e.g. a command-palette search field) skip this
 * part and sit directly in `DialogMain` so they keep equal side gutters.
 */
export function DialogHeader({ render, ...props }: DialogHeaderProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogHeaderVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
