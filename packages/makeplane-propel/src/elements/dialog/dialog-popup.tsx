import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type DialogPopupHeight,
  type DialogPopupSize,
  type DialogPopupVariantProps,
  dialogPopupVariants,
} from "./variants";

export type { DialogDensity, DialogPopupHeight, DialogPopupSize } from "./variants";

export type DialogPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<DialogPopupVariantProps, "size" | "height"> & {
    /**
     * Dialog width: `xs` 480 px, `sm` 576 px, `md` 672 px, `lg` 800 px, `xl` 1000 px, or `full`,
     * which fills the viewport minus an 80 px margin on every edge and pins the height as well.
     *
     * @default "md"
     */
    size?: DialogPopupSize;
    /**
     * Dialog height. `auto` (default) sizes to content up to the viewport ceiling. `fixed` pins 700
     * px so split chrome does not jump when the active pane changes. Use `size="full"` when the
     * popup should fill the viewport instead.
     *
     * @default "auto"
     */
    height?: DialogPopupHeight;
  };

/**
 * The card that holds the dialog content, hung 80 px from the top of the viewport. Base-UI-agnostic
 * — graft the dialog behavior in `components` via `<BaseDialog.Popup render={<DialogPopup />} />`.
 *
 * Compose optional `DialogToolbar` + `DialogMain` + `DialogActions` inside, and pin dismiss in
 * `DialogCloseGroup`. Gutter of Toolbar / Main / Actions / Aside is a ready-made concern: the
 * components-tier wrappers read `size` and `density` from context and pass them as props (rules 1,
 * 7).
 */
export function DialogPopup({ size, height, render, ...props }: DialogPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: dialogPopupVariants({ size, height }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
