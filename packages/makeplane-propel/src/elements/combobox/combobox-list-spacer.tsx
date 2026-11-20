import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { comboboxListSpacerVariants } from "./variants";

export type ComboboxListSpacerProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> & {
  /** Total measured block extent of the virtualized collection, in pixels. */
  extent: number;
};

/** Reserves scroll space for a windowed list without rendering offscreen options. */
export function ComboboxListSpacer({ extent, render, ...props }: ComboboxListSpacerProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps(
      { role: "presentation", className: comboboxListSpacerVariants(), style: { height: extent } },
      props,
    ),
  });
}
