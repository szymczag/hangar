import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type PillGroupVariantProps, pillGroupVariants } from "./variants";

export type { PillGroupSize } from "./variants";

export type PillGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  PillGroupVariantProps;

/**
 * The styled connected frame around `Pill`s and `IconPill`s — overlapped borders that read as one
 * divider, outer corners rounded and inner ones flattened, and the hovered/focused/open segment
 * lifted so it owns the seam it shares. The segments keep their own chrome; the frame only owns how
 * they sit together. Base-UI-agnostic (there is no Base UI pill-group primitive); the `components`
 * ready-made adds the `group` role and shares one `size` with every segment via context.
 */
export function PillGroup({ size, render, ...props }: PillGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: pillGroupVariants({ size }) };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
