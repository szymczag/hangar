import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type BannerTitleVariantProps, bannerTitleVariants } from "./variants";

export type BannerTitleProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  BannerTitleVariantProps;

/** The banner's headline, stacked above the `BannerDescription` inside the `BannerBody`. */
export function BannerTitle({ placement, size, render, ...props }: BannerTitleProps) {
  // `data-slot` lets the root detect a missing title and drop the icon slot to the description's
  // line height (see `bannerVariants`). Intersected onto ElementProps because the React DOM typings
  // don't admit arbitrary `data-*` keys on the annotated object, though the attribute is valid.
  const defaultProps: useRender.ElementProps<"div"> & { "data-slot": string } = {
    "data-slot": "banner-title",
    className: bannerTitleVariants({ placement, size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
