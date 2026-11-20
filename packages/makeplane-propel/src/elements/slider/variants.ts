import { cva, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// The root only stacks the (optional) header row over the control; the label/value layout
// lives on `SliderHeader`, not here.
export const sliderVariants = cva("flex w-full flex-col gap-2");

// The header row above the control: label at the inline-start, value readout at the inline-end.
export const sliderHeaderVariants = cva("flex items-center justify-between gap-3");

// A step below the label, matching the `Meter` and `LinearProgress` readouts — the same
// role in the same header layout.
export const sliderValueVariants = cva("text-caption-md-regular text-secondary");

// Control height must accommodate the thumb. The track bar height is always the same (h-1),
// but the thumb and its surrounding hit-area grow with `size`.
export const sliderControlVariants = cva("flex items-center", {
  variants: {
    size: {
      sm: "h-4",
      md: "h-5",
      lg: "h-6",
    },
  },
});

// Track height is always the same (thin bar) per the design spec.
export const sliderTrackVariants = cva("relative h-1 w-full rounded-full bg-layer-3");
export const sliderIndicatorVariants = cva("absolute h-full rounded-full bg-accent-primary");

// Thumb size is fixed per size variant. Focus ring, disabled state, and shape are always the same.
export const sliderThumbVariants = cva(
  [
    "block rounded-full border-sm border-accent-strong bg-layer-1 shadow-raised-100 outline-none",
    "focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2",
    "data-disabled:cursor-not-allowed data-disabled:opacity-60",
  ].join(" "),
  {
    variants: {
      size: {
        sm: "size-3",
        md: "size-4",
        lg: "size-5",
      },
    },
  },
);

// `FieldLabel`'s `md` treatment (13px medium), fixed: `Slider`'s `size` is thumb geometry — a
// 12/16/20px thumb — which has no business setting text size, so there is nothing to thread.
// Puts `SliderLabel` (13) over `SliderValue` (12), the same label/value pair `Meter` and
// `LinearProgress` use.
export const sliderLabelVariants = cva("text-body-xs-medium text-primary");

export type SliderSize = NonNullable<VariantProps<typeof sliderControlVariants>["size"]>;
export type SliderControlVariantProps = StrictVariantProps<typeof sliderControlVariants>;
export type SliderThumbVariantProps = StrictVariantProps<typeof sliderThumbVariants>;
