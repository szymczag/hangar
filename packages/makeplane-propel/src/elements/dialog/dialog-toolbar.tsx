import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type DialogDensity,
  type DialogToolbarSize,
  type DialogToolbarVariantProps,
  dialogToolbarVariants,
} from "./variants";

export type { DialogDensity, DialogToolbarSize } from "./variants";

export type DialogToolbarProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<DialogToolbarVariantProps, "size" | "density"> & {
    /**
     * Gutter tier, matching the popup `size` it sits in: 16 px start at every rung, 40 px end so
     * content clears the corner dismiss; 48 × 18 px at `full`.
     *
     * @default "md"
     */
    size?: DialogToolbarSize;
    /**
     * Compactness. `comfortable` (default) lets `size` pick the gutter; `compact` keeps 16 px at
     * every size, including `full`.
     *
     * @default "comfortable"
     */
    density?: DialogDensity;
  };

/**
 * Top chrome of the dialog popup, sibling of `DialogMain`. Bottom border spans the popup the way
 * `DialogActions`' top border does — do not put a divider on a child inside Main. Compose a start
 * cluster (tabs, title) and an optional end control. End padding clears the absolute
 * `DialogCloseGroup`, so that control is not under the dismiss.
 */
export function DialogToolbar({ size, density, render, ...props }: DialogToolbarProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: dialogToolbarVariants({ size, density }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
