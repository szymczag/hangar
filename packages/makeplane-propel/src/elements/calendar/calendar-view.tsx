import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewVariants } from "./variants";

export type CalendarViewProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** Bare 280px month/year view; the containing popover or card provides the surface. */
export function CalendarView({ render, ...props }: CalendarViewProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: calendarViewVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
