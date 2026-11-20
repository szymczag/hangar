import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ComboboxPopupVariantProps, comboboxPopupVariants } from "./variants";

export type { ComboboxPopupElevation } from "./variants";

export type ComboboxPopupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ComboboxPopupVariantProps;

/**
 * The styled combobox list surface. Base-UI-agnostic — graft the popup behavior in `components` via
 * `<BaseCombobox.Popup render={<ComboboxPopup elevation="…" />} />`. `raised` is the standalone
 * surface; `flat` is padding-only for use inside an `OverlayPanel`.
 */
export function ComboboxPopup({ elevation, render, ...props }: ComboboxPopupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: comboboxPopupVariants({ elevation }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
