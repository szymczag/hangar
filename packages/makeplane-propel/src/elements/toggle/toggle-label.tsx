import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { toggleLabelVariants } from "./variants";

export type ToggleLabelProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The toggle's single-line label. Shrinks and truncates instead of wrapping. When `children` is a
 * string, bakes a native `title` so hover recovers the full text past the 120px cap; pass `title`
 * explicitly to override (or `title=""` to suppress).
 */
export function ToggleLabel({ render, children, title, ...props }: ToggleLabelProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: toggleLabelVariants(),
    children,
    title: title ?? (typeof children === "string" ? children : undefined),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
