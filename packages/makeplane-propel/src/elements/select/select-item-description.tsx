import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { selectItemDescriptionVariants } from "./variants";

export type SelectItemDescriptionProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** A muted second line beneath an option's label. A row carrying one takes `layout="stacked"`. */
export function SelectItemDescription({ render, ...props }: SelectItemDescriptionProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: selectItemDescriptionVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
