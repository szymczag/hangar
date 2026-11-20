import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type LogoSpinnerImageVariantProps, logoSpinnerImageVariants } from "./variants";

export type { LogoSpinnerMotion, LogoSpinnerSize, LogoSpinnerTheme } from "./variants";

/** Props for {@link LogoSpinnerImage}. */
export type LogoSpinnerImageProps = Omit<
  useRender.ComponentProps<"img">,
  "className" | "style" | "height" | "width"
> &
  LogoSpinnerImageVariantProps;

/**
 * One theme's brand mark in one motion mode (`size` `sm` 24px / `md` 44px / `fluid` 24px stepping
 * to 44px, `theme` `light` / `dark`, `motion` `animated` (default) / `still`). Pass the asset as
 * `src`; the ready-made `components/logo-spinner` resolves the GIF pair and the still pair that
 * ship with the package. All four images are rendered and CSS paints the one matching the active
 * `data-theme` and the viewer's motion preference, so no JS runs on a theme flip and a
 * reduced-motion viewer sees the fully drawn mark instead of the animation.
 */
export function LogoSpinnerImage({ size, theme, motion, render, ...props }: LogoSpinnerImageProps) {
  const defaultProps: useRender.ElementProps<"img"> = {
    className: logoSpinnerImageVariants({ size, theme, motion }),
  };
  return useRender({ defaultTagName: "img", render, props: mergeProps(defaultProps, props) });
}
