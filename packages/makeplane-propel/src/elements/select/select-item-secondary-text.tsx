import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectItemSecondaryTextVariants } from "./variants";

export type SelectItemSecondaryTextProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** Muted text shown inline after an option's label. */
export function SelectItemSecondaryText({ render, ...props }: SelectItemSecondaryTextProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: selectItemSecondaryTextVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
