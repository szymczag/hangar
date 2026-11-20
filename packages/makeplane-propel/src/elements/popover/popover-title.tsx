import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { popoverTitleVariants } from "./variants";

/** Props for {@link PopoverTitle}. */
export type PopoverTitleProps = Omit<useRender.ComponentProps<"h2">, "className" | "style">;

/**
 * The panel's accessible heading — `text-body-sm-medium` per the compact text card. Wraps with
 * word-break instead of truncating. Diverges from the shared `internal/overlay-title` "md" step
 * (`semibold`); this family binds the lighter `medium` weight, so it keeps its own recipe.
 */
export function PopoverTitle({ render, ...props }: PopoverTitleProps) {
  const defaultProps: useRender.ElementProps<"h2"> = { className: popoverTitleVariants() };
  return useRender({ defaultTagName: "h2", render, props: mergeProps(defaultProps, props) });
}
