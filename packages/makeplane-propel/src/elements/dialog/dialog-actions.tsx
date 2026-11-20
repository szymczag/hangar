import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type DialogActionsSize,
  type DialogDensity,
  type DialogActionsVariantProps,
  dialogActionsVariants,
} from "./variants";

export type { DialogActionsSize, DialogDensity } from "./variants";

export type DialogActionsProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<DialogActionsVariantProps, "size" | "density"> & {
    /**
     * Gutter tier, matching the popup `size` it sits in: 16 px at every rung, 48 × 18 px at `full`.
     *
     * @default "md"
     */
    size?: DialogActionsSize;
    /**
     * Compactness. `comfortable` (default) lets `size` pick the gutter; `compact` keeps 16 px at
     * every size, including `full`.
     *
     * @default "comfortable"
     */
    density?: DialogDensity;
  };

/**
 * The footer of the dialog popup. Top border separates it from `DialogMain`. Compose an optional
 * `DialogInfo` (flexes to the inline-start) followed by action buttons (ghost / secondary /
 * primary) with a 12 px gap.
 */
export function DialogActions({ size, density, render, ...props }: DialogActionsProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: dialogActionsVariants({ size, density }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
