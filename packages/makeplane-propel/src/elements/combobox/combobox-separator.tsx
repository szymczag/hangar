import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxSeparatorVariants } from "./variants";

export type ComboboxSeparatorProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * A styled thin divider between groups of items. Base UI's combobox has no Separator primitive, so
 * this is a styled element composed into the list — same chrome as the dropdown menu divider.
 */
export function ComboboxSeparator({ render, ...props }: ComboboxSeparatorProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: comboboxSeparatorVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
