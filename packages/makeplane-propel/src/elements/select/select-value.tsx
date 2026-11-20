import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectValueVariants } from "./variants";

export type SelectValueProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The styled selected-value display inside a trigger — single-line, shrinks and truncates instead
 * of wrapping. When `children` is a string, bakes a native `title` so hover recovers the full text
 * past the truncation point; pass `title` explicitly to override (or `title=""` to suppress).
 * Base-UI-agnostic — graft the value behavior in `components` via `<BaseSelect.Value
 * render={<SelectValue/>} />`.
 */
export function SelectValue({ render, children, title, ...props }: SelectValueProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: selectValueVariants(),
    children,
    title: title !== undefined ? title : typeof children === "string" ? children : undefined,
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
