import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewNavVariants } from "./variants";

export type CalendarViewNavProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** Groups the two 28px previous and next controls with a 4px gap. */
export function CalendarViewNav({ render, ...props }: CalendarViewNavProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: calendarViewNavVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
