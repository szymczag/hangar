import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { radioDotClass } from "./radio-circle";

export type RadioDotProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The 8px selected dot that sits inside a radio circle, painted with the ring's `currentColor` so
 * the two never drift apart.
 *
 * Shared, not per-family (rule 4a): the standalone `Radio` and both menu radio rows render the
 * identical styled element, so it lives here and is grafted per host rather than re-spelled. It was
 * re-spelled — the menus drew their dot as a lucide `Circle` scaled to `size-2`, which renders a
 * 6.67px stroked-and-filled circle inside an 8px box, visibly softer and smaller than the span the
 * standalone control used. One element now, one geometry.
 */
export function RadioDot({ render, ...props }: RadioDotProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: radioDotClass };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
