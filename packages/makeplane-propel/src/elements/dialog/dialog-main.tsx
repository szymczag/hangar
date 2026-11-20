import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type DialogDensity,
  type DialogMainSize,
  type DialogMainVariantProps,
  dialogMainVariants,
} from "./variants";

export type { DialogDensity, DialogMainSize } from "./variants";

export type DialogMainProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<DialogMainVariantProps, "size" | "density" | "inPanes"> & {
    /**
     * Gutter tier, matching the popup `size` it sits in: 16 px at every rung, 48 px at `full`.
     *
     * @default "md"
     */
    size?: DialogMainSize;
    /**
     * Compactness. `comfortable` (default) lets `size` pick the gutter; `compact` keeps 16 px at
     * every size, including `full`.
     *
     * @default "comfortable"
     */
    density?: DialogDensity;
    /**
     * True when this part sits inside `DialogPanes`. Derived by the ready-made; pass it at the
     * elements tier so the pane child can fill the row.
     *
     * @default false
     */
    inPanes?: boolean;
  };

/**
 * The padded top section of the dialog popup: stacks optional `DialogProgression`, `DialogHeader` /
 * `DialogHeading`, and the scrollable `DialogBody`. Content-sized; when the popup hits its ceiling
 * this section shrinks (`min-h-0`) while `DialogActions` stays put, so the footer is always visible
 * and the body scrolls. Inside `DialogPanes` it fills the width beside `DialogAside`. The absolute
 * close overlays the top-end — it does not widen the end gutter.
 */
export function DialogMain({ size, density, inPanes, render, ...props }: DialogMainProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: dialogMainVariants({ size, density, inPanes }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
