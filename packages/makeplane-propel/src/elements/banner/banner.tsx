import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type BannerVariant, type BannerVariantProps, bannerVariants } from "./variants";

export type { BannerVariant, BannerPlacement, BannerSize } from "./variants";

// warning/danger are time-sensitive problems → `alert` (assertive). The calmer
// variants are advisory → `status` (polite). Picks the right live-region semantics.
const variantRole: Record<BannerVariant, "status" | "alert"> = {
  neutral: "status",
  info: "status",
  accent: "status",
  warning: "alert",
  danger: "alert",
};

export type BannerProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  BannerVariantProps;

/**
 * The banner strip/card. Lays out its parts (`BannerIcon`, `BannerBody`, `BannerActions`, and an
 * optional dismiss `IconButton`) in a row. The `role`/`aria-live` come from the variant so
 * assistive tech announces problems assertively and advisories politely; consumers can override via
 * spread.
 */
export function Banner({ placement, size, variant, render, ...props }: BannerProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    role: variantRole[variant],
    className: bannerVariants({ placement, size, variant }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
