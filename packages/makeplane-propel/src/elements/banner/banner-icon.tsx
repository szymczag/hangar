import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type BannerIconVariantProps, bannerIconVariants } from "./variants";

export type BannerIconProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> &
  BannerIconVariantProps;

/**
 * The leading icon slot at the banner's inline-start (the Figma intent icon). Sizes its single
 * child to the banner's node size and tints it per `variant`, so callers pass a bare icon.
 * Decorative (the message carries the meaning), so it is `aria-hidden`.
 */
export function BannerIcon({ placement, variant, size, render, ...props }: BannerIconProps) {
  // `data-slot` is the hook `bannerVariants` uses to resize this slot when there is no title.
  const defaultProps: useRender.ElementProps<"span"> & { "data-slot": string } = {
    "aria-hidden": true,
    "data-slot": "banner-icon",
    className: bannerIconVariants({ placement, variant, size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
