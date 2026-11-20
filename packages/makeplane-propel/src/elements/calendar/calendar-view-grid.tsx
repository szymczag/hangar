import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { calendarViewGridVariants } from "./variants";

export type CalendarViewGridProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/** Three columns and four 40px rows distributed across the 240px month/year body. */
export function CalendarViewGrid({ render, ...props }: CalendarViewGridProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: calendarViewGridVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
