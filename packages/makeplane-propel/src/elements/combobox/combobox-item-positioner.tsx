import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxItemPositionerVariants } from "./variants";

export type ComboboxItemPositionerProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> & {
  /** Offset from the start of the virtualized list, in pixels. */
  offset: number;
};

/** Positions a measured option without changing the option's own chrome. */
export function ComboboxItemPositioner({ offset, render, ...props }: ComboboxItemPositionerProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps(
      {
        role: "presentation",
        className: comboboxItemPositionerVariants(),
        style: { transform: `translateY(${offset}px)` },
      },
      props,
    ),
  });
}
