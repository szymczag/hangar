import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectSeparatorVariants } from "./variants";

export type SelectSeparatorProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * A thin divider between groups of options — the same chrome as the menu divider. Composed straight
 * into the list in `components`, not grafted onto Base UI's `Select.Separator`, whose
 * `role="separator"` a listbox may not own.
 */
export function SelectSeparator({ render, ...props }: SelectSeparatorProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: selectSeparatorVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
