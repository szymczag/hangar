import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type BannerDescriptionVariantProps, bannerDescriptionVariants } from "./variants";

export type BannerDescriptionProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  BannerDescriptionVariantProps;

/**
 * The banner's supporting message, stacked below the `BannerTitle` inside the `BannerBody`. One
 * step smaller than the title: 13/20 in `md`, 12/18 in `sm`.
 */
export function BannerDescription({ size, render, ...props }: BannerDescriptionProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: bannerDescriptionVariants({ size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
