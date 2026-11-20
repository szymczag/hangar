import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewHeaderVariants } from "./variants";

export type CalendarViewHeaderProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** The 28px row holding the caption on the left and navigation on the right. */
export function CalendarViewHeader({ render, ...props }: CalendarViewHeaderProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: calendarViewHeaderVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
