import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { dialogProgressionVariants } from "./variants";

export type DialogProgressionProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Optional step row at the top of `DialogHeader`: compose a back `IconButton` (size `xs`, variant
 * `ghost`) and the step label as children. Caption-md tertiary chrome is baked in. Laid out in
 * normal flow (not Figma's absolute hang into the gutter) — the glyph sits on the Main padding
 * edge; consumers supply the back handler.
 */
export function DialogProgression({ render, ...props }: DialogProgressionProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: dialogProgressionVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
