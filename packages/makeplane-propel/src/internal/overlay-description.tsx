import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "./variant-props";

/**
 * The shared overlay description text, grafted onto any Base UI `*.Description` behavior in
 * `components` (`<BaseDrawer.Description render={<OverlayDescription size="md" />}>`). Renders the
 * secondary supporting copy under an overlay's title. Byte-identical across adopting families, so
 * it lives here rather than being copied per family (rule 4a). Dialog diverged to family-owned
 * `dialogDescriptionVariants` (body-xs tertiary). Alert Dialog uses a family-local description
 * (`text-body-sm-regular text-secondary`) rather than this shared recipe.
 *
 * Adopted by: `popover`, `preview-card`, `drawer` (`size="md"` → `body-xs`).
 */
export const overlayDescriptionVariants = cva("", {
  variants: {
    size: {
      md: "text-body-xs-regular text-secondary",
      lg: "text-body-sm-regular text-secondary",
    },
  },
});

export type OverlayDescriptionSize = NonNullable<
  VariantProps<typeof overlayDescriptionVariants>["size"]
>;
export type OverlayDescriptionVariantProps = StrictVariantProps<typeof overlayDescriptionVariants>;

export type OverlayDescriptionProps = Omit<useRender.ComponentProps<"p">, "className" | "style"> &
  OverlayDescriptionVariantProps;

export function OverlayDescription({ size, render, ...props }: OverlayDescriptionProps) {
  const defaultProps: useRender.ElementProps<"p"> = {
    className: overlayDescriptionVariants({ size }),
  };
  return useRender({ defaultTagName: "p", render, props: mergeProps(defaultProps, props) });
}
