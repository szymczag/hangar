import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { listItemCounterVariants } from "./variants";

export type ListItemCounterProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/** The row's trailing count chip (e.g. an unread count). */
export function ListItemCounter({ render, ...props }: ListItemCounterProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: listItemCounterVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
