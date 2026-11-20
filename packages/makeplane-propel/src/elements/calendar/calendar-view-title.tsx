import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewTitleVariants } from "./variants";

export type CalendarViewTitleProps = Omit<useRender.ComponentProps<"span">, "className" | "style">;

/** The 18px semibold caption, including the year range in year view. */
export function CalendarViewTitle({ render, ...props }: CalendarViewTitleProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: calendarViewTitleVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
