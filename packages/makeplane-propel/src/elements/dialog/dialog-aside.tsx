import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { ScrollportXClip } from "../../internal/scrollport-x-clip";
import {
  type DialogAsideSize,
  type DialogDensity,
  type DialogAsideVariantProps,
  dialogAsideClipVariants,
  dialogAsideVariants,
} from "./variants";

export type { DialogAsideSize, DialogDensity } from "./variants";

export type DialogAsideProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<DialogAsideVariantProps, "size" | "density"> & {
    /**
     * Gutter tier, matching the popup `size` it sits in: 16 px start at every rung, 48 px at
     * `full`.
     *
     * @default "md"
     */
    size?: DialogAsideSize;
    /**
     * Compactness. `comfortable` (default) lets `size` pick the gutter; `compact` keeps 16 px at
     * every size, including `full`.
     *
     * @default "comfortable"
     */
    density?: DialogDensity;
  };

/**
 * A fixed-width (280 px) start-side column inside `DialogPanes`, beside `DialogMain`. Stretches to
 * the panes' height so its end seam is the full popup. Scrolls on its own. Holds navigation for the
 * dialog's content — a step list, a section list — supplied by the consumer. Pass `tabIndex={0}`
 * when its content can overflow.
 */
export function DialogAside({ size, density, render, children, ...props }: DialogAsideProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: dialogAsideVariants({ size, density }) }, props, {
      children: <ScrollportXClip className={dialogAsideClipVariants()}>{children}</ScrollportXClip>,
    }),
  });
}
