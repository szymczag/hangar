import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewSwitchVariants } from "./variants";

export type CalendarViewSwitchProps = Omit<
  useRender.ComponentProps<"button">,
  "className" | "style"
>;

/** The caption button; the caller supplies a 14px chevron in an internal `NodeSlot`. */
export function CalendarViewSwitch({ render, ...props }: CalendarViewSwitchProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: calendarViewSwitchVariants(),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
