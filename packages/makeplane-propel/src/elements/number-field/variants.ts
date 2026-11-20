import { type VariantProps, cva, cx } from "class-variance-authority";

import { controlGroupClass } from "../../internal/control-group";
import { controlInputClass } from "../../internal/control-input";
import { type StrictVariantProps } from "../../internal/variant-props";

export const numberFieldVariants = cva("flex min-w-0 flex-col gap-1.5");

// Outer frame owns height so steppers sit one rung below (Figma: sm → 20px buttons, md → 24,
// lg → 28). Height tokens are border-box and include `border-sm` (1px): use `p-px` (1px), not
// `p-0.5`, so content = h − 2×border − 2×pad matches the stepper square (24−2−2 = 20, …). Outer
// edge → button is still 2px (1px stroke + 1px pad), so IconButton's xs 2px halo meets the frame
// edge for WCAG 2.5.8. No `overflow-hidden` (halo must paint). −/+ are separated by the input so
// neighboring halos never intersect. No `xs` (20px) frame — contiguous/grouped controls omit halo
// rungs (see size-scale + ButtonGroupButton). Raised rest shadow clears on focus and when disabled.
export const numberFieldGroupVariants = cva(
  cx(
    controlGroupClass,
    "w-fit items-center p-px shadow-raised-100 focus-within:shadow-none",
    "has-[:disabled]:shadow-none data-disabled:shadow-none",
  ),
  {
    variants: {
      size: {
        sm: "h-(--control-height-sm) rounded-(--control-radius-sm)",
        md: "h-(--control-height-md) rounded-(--control-radius-md)",
        lg: "h-(--control-height-lg) rounded-(--control-radius-lg)",
      },
    },
  },
);

// Value cell: medium type + Figma min-width floor (36/40). `field-sizing-content` grows with the
// value where supported; `NumberFieldInput` also defaults the native ch `size` so older Safari/
// Firefox (in browserslist) stay compact. Height from group.
export const numberFieldInputVariants = cva(
  cx(controlInputClass, "field-sizing-content h-full px-1 text-center"),
  {
    variants: {
      size: {
        sm: "min-w-9 text-body-xs-medium",
        md: "min-w-10 text-body-xs-medium",
        lg: "min-w-10 text-body-sm-medium",
      },
    },
  },
);

export type NumberFieldGroupVariantProps = StrictVariantProps<typeof numberFieldGroupVariants>;
export type NumberFieldInputVariantProps = StrictVariantProps<typeof numberFieldInputVariants>;

// Shared size type so group, input, and stepper guidance stay in sync.
export type NumberFieldSize = NonNullable<VariantProps<typeof numberFieldGroupVariants>["size"]>;

/**
 * IconButton `size` that keeps steppers flush inside a field of the given `size` (Figma: field sm →
 * button xs, md → sm, lg → md).
 */
export const numberFieldStepperSize = {
  sm: "xs",
  md: "sm",
  lg: "md",
} as const satisfies Record<NumberFieldSize, "xs" | "sm" | "md">;

export type NumberFieldStepperSize = (typeof numberFieldStepperSize)[NumberFieldSize];
