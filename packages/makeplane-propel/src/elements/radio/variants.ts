import { cva, cx, type VariantProps } from "class-variance-authority";

import { optionGroupDensityClasses, optionGroupVariants } from "../../internal/option-group";
import { radioCircleVariants, radioDotClass } from "../../internal/radio-circle";
import { type StrictVariantProps } from "../../internal/variant-props";

// The shared 16px ring (`internal/radio-circle`), which the menu / context-menu radio indicators
// render too — mirrors `checkboxVariants = checkboxBoxVariants` in `elements/checkbox`.
//
// The resting `bg-layer-1` fill lives here rather than in the shared circle: a standalone radio sits
// on a form surface and wants an opaque well, while a menu row's marker must let the row's
// translucent highlight wash through the way the menu checkbox box does.
export const radioVariants = cva(cx(radioCircleVariants(), "bg-layer-1"));

// The inner dot: 8px filled with the Root's `currentColor`, only present while selected (Base UI
// mounts the Indicator when checked).
export const radioIndicatorVariants = cva(radioDotClass);

export const radioGroupVariants = optionGroupVariants;

export type RadioGroupDensity = NonNullable<VariantProps<typeof radioGroupVariants>["density"]>;

export type RadioGroupVariantProps = StrictVariantProps<typeof radioGroupVariants>;

const radioGroupOptionsDefaultVariants = {
  orientation: "vertical",
} as const;

export const radioGroupOptionsVariants = cva("flex min-w-0", {
  variants: {
    density: optionGroupDensityClasses,
    orientation: {
      vertical: "flex-col",
      horizontal: "flex-row flex-wrap items-start",
    },
  },
  defaultVariants: radioGroupOptionsDefaultVariants,
});

type RadioGroupOptionsVariantConfig = VariantProps<typeof radioGroupOptionsVariants>;

export type RadioGroupOptionsOrientation = NonNullable<
  RadioGroupOptionsVariantConfig["orientation"]
>;

export type RadioGroupOptionsVariantProps = StrictVariantProps<
  typeof radioGroupOptionsVariants,
  keyof typeof radioGroupOptionsDefaultVariants
>;
