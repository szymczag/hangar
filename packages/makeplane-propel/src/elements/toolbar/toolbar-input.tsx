import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ToolbarInputVariantProps, toolbarInputVariants } from "./variants";

// The native `<input size>` (width in characters) is omitted: the styling axis wins the name,
// exactly as on `Input` and `NumberFieldInput` (rule 6b).
export type ToolbarInputProps = Omit<
  useRender.ComponentProps<"input">,
  "className" | "style" | "size"
> &
  ToolbarInputVariantProps;

/**
 * The styled inline text input for a toolbar (a miniature field on the shared control surface,
 * size-matched to the items). Base-UI-agnostic — graft in `components` via `<BaseToolbar.Input
 * render={<ToolbarInput size=… />} />`.
 */
export function ToolbarInput({ size, render, ...props }: ToolbarInputProps) {
  const defaultProps: useRender.ElementProps<"input"> = {
    className: toolbarInputVariants({ size }),
  };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
