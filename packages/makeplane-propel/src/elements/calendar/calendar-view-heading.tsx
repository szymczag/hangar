import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewHeadingVariants } from "./variants";

export type CalendarViewHeadingProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** Aligns the month and year caption switches in a single row. */
export function CalendarViewHeading({ render, ...props }: CalendarViewHeadingProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: calendarViewHeadingVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
