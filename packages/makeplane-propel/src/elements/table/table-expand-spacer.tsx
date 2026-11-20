import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { tableExpandSpacerVariants } from "./variants";

export type TableExpandSpacerProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/**
 * The empty 16px box a row without children renders in place of a `TableExpandTrigger`, so every
 * title in the column starts at the same edge. Decorative, so it is hidden from assistive tech.
 */
export function TableExpandSpacer({ render, ...props }: TableExpandSpacerProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: tableExpandSpacerVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
