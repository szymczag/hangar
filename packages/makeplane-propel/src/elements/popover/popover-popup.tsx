import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  popoverPopupVariants,
  type PopoverPopupVariant,
  type PopoverPopupVariantProps,
} from "./variants";

export type { PopoverPopupVariant };

export type PopoverPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<PopoverPopupVariantProps, "variant"> & {
    /**
     * Panel look. `rich` is the padded content panel for forms and arbitrary children; `text` is
     * the compact 296px title + description card.
     *
     * @default "rich"
     */
    variant?: PopoverPopupVariant;
  };

/**
 * The anchored panel surface. `rich` is the padded content panel; `text` is the compact title +
 * description card. Base-UI-agnostic — graft in `components` via `<BasePopover.Popup
 * render={<PopoverPopup />} />`.
 */
export function PopoverPopup({ variant, render, ...props }: PopoverPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: popoverPopupVariants({ variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
