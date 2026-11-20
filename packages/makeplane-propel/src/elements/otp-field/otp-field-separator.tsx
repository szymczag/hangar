import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { otpFieldSeparatorVariants } from "./variants";

export type OTPFieldSeparatorProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * A styled divider between groups of slots, e.g. `123-456`. Decorative — `aria-hidden` by default,
 * like `BreadcrumbSeparator`. Base-UI-agnostic; graft in `components` via `<BaseOTPField.Separator
 * render={<OTPFieldSeparator/>} />`.
 */
export function OTPFieldSeparator({ render, ...props }: OTPFieldSeparatorProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    "aria-hidden": true,
    className: otpFieldSeparatorVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
