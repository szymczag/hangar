import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type IconToggleVariantProps, iconToggleVariants } from "./variants";

export type IconToggleProps = Omit<useRender.ComponentProps<"button">, "className" | "style"> &
  IconToggleVariantProps;

/**
 * The styled square icon-only toggle button. Base-UI-agnostic — graft the `Toggle` behavior in
 * `components` via `<BaseToggle render={<IconToggle variant=… size=… />} />`. `variant` is the look
 * (`secondary`·`ghost`); `size` is the square scale (`xs`·`sm`·`md`). Pressed/disabled are control
 * state Base UI reflects as `data-*`.
 */
export function IconToggle({ variant, size, render, ...props }: IconToggleProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: iconToggleVariants({ variant, size }),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
