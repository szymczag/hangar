import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { logoSpinnerVariants } from "./variants";

/** Props for {@link LogoSpinner}. */
export type LogoSpinnerProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The styled box of the brand loading mark. Compose the `LogoSpinnerImage` pair (one per theme)
 * inside it; the ready-made `components/logo-spinner` supplies both images, their asset URLs and
 * the `img` role.
 */
export function LogoSpinner({ render, ...props }: LogoSpinnerProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: logoSpinnerVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
