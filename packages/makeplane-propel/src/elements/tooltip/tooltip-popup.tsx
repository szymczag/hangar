import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  tooltipPopupVariants,
  type TooltipLayout,
  type TooltipPopupVariantProps,
} from "./variants";

export type { TooltipLayout } from "./variants";

export type TooltipPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<TooltipPopupVariantProps, "layout"> & {
    /**
     * Content arrangement. `single` is the compact Figma chip and wraps long labels within 500px;
     * `stacked` is the multiline description layout (body type, larger radius, 500px maximum width,
     * shortcut below).
     *
     * @default "single"
     */
    layout?: TooltipLayout;
  };

/**
 * The styled tooltip surface — adaptive popup with caption/body text, radius, shadow, and the gap
 * to the shortcut. `layout` switches Figma singleline vs multiline chrome. Base-UI-agnostic; graft
 * in `components` via `<BaseTooltip.Popup render={<TooltipPopup/>} />`.
 */
export function TooltipPopup({ layout = "single", render, ...props }: TooltipPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: tooltipPopupVariants({ layout }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
