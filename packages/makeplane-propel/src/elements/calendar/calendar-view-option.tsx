import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewOptionVariants } from "./variants";

export type CalendarViewOptionProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style"
>;

/** A month or year choice; `data-active=""` gives the displayed value its neutral fill. */
export function CalendarViewOption({ render, ...props }: CalendarViewOptionProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: calendarViewOptionVariants(),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
