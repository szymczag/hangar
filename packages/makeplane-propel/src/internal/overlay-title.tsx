import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "./variant-props";

/**
 * The shared overlay heading, grafted onto any Base UI `*.Title` behavior in `components`
 * (`<BaseDrawer.Title render={<OverlayTitle size="xl" />}>`). Anchored/modal overlay families that
 * share this semibold primary heading (differing only in size) use this recipe rather than copying
 * it per family (rule 4a). Dialog diverged to family-owned `dialogTitleVariants` (h5-medium). Alert
 * Dialog uses a family-local title (`text-h5-medium`) rather than this shared recipe.
 *
 * Adopted by: drawer (`size="xl"`, body-md). Popover and preview-card keep family-owned titles
 * (`body-sm-medium`) because they bind a lighter weight than this recipe's `md` step.
 */
export const overlayTitleVariants = cva("text-primary", {
  variants: {
    size: {
      md: "text-body-sm-semibold",
      lg: "text-h6-semibold",
      xl: "text-body-md-semibold",
    },
  },
});

type OverlayTitleVariantConfig = VariantProps<typeof overlayTitleVariants>;
export type OverlayTitleSize = NonNullable<OverlayTitleVariantConfig["size"]>;
export type OverlayTitleVariantProps = StrictVariantProps<typeof overlayTitleVariants>;

export type OverlayTitleProps = Omit<useRender.ComponentProps<"h2">, "className" | "style"> &
  OverlayTitleVariantProps;

export function OverlayTitle({ size, render, ...props }: OverlayTitleProps) {
  const defaultProps: useRender.ElementProps<"h2"> = {
    className: overlayTitleVariants({ size }),
  };
  return useRender({ defaultTagName: "h2", render, props: mergeProps(defaultProps, props) });
}
