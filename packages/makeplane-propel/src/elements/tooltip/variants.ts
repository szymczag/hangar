import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

const tooltipPopupDefaultVariants = {
  layout: "single",
} as const;

/**
 * Tooltip surface. `layout` mirrors Figma singleline / multiline: a compact row that wraps long
 * labels vs a stacked description with the shortcut beneath. Shared chrome (fill, border, shadow,
 * padding) stays on the base; type, radius, direction, and gap switch per layout.
 */
export const tooltipPopupVariants = cva(
  // Figma sets `word-break: break-word` on both variants. `overflow-wrap: anywhere` rather than
  // `break-word` because the label is a bare text child: it becomes an anonymous flex item whose
  // automatic minimum size is its longest word, and only `anywhere` lets that min-content size
  // shrink. Without it a long unbroken token still paints outside the surface — measured at 984px
  // of content in a 498px box.
  // Base UI subtracts collision padding from `--available-width`; the 100vw fallback also keeps
  // the standalone element usable without a positioner.
  "flex max-w-[min(500px,var(--available-width,100vw))] border-sm border-subtle-1 bg-layer-2 px-2 py-1.5 wrap-anywhere text-primary shadow-overlay-200",
  {
    variants: {
      layout: {
        single: "items-center gap-3 rounded-md text-caption-md-regular",
        stacked: "flex-col items-start gap-1.5 rounded-lg text-body-xs-regular",
      },
    },
    defaultVariants: tooltipPopupDefaultVariants,
  },
);

type TooltipPopupVariantConfig = VariantProps<typeof tooltipPopupVariants>;
export type TooltipLayout = NonNullable<TooltipPopupVariantConfig["layout"]>;

export type TooltipPopupVariantProps = StrictVariantProps<
  typeof tooltipPopupVariants,
  keyof typeof tooltipPopupDefaultVariants
>;

export const tooltipArrowVariants = cva(
  cx(
    "size-2 rotate-45 border-sm border-subtle-1 bg-layer-2",
    "data-[side=bottom]:top-[-3px] data-[side=bottom]:[clip-path:polygon(0_0,100%_0,0_100%)]",
    "data-[side=top]:bottom-[-3px] data-[side=top]:[clip-path:polygon(100%_0,100%_100%,0_100%)]",
    "data-[side=left]:right-[-3px] data-[side=left]:[clip-path:polygon(0_0,100%_0,100%_100%)]",
    "data-[side=right]:left-[-3px] data-[side=right]:[clip-path:polygon(0_0,0_100%,100%_100%)]",
    "data-[side=inline-start]:inset-e-[-3px] data-[side=inline-start]:[clip-path:polygon(0_0,100%_0,100%_100%)] rtl:data-[side=inline-start]:[clip-path:polygon(0_0,0_100%,100%_100%)]",
    "data-[side=inline-end]:inset-s-[-3px] data-[side=inline-end]:[clip-path:polygon(0_0,0_100%,100%_100%)] rtl:data-[side=inline-end]:[clip-path:polygon(0_0,100%_0,100%_100%)]",
  ),
);
