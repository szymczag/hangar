import { cva, cx, type VariantProps } from "class-variance-authority";

import { controlGroupClass, controlSize } from "../../internal/control-group";
import { controlInputClass } from "../../internal/control-input";
import { type StrictVariantProps } from "../../internal/variant-props";

export const inputVariants = cva(cx(controlInputClass, "flex-1"), {
  variants: {
    size: {
      md: "text-body-xs-regular",
      lg: "text-body-sm-regular",
      xl: "text-body-sm-regular",
      "2xl": "text-body-md-regular",
    },
  },
});

type InputVariantConfig = VariantProps<typeof inputVariants>;

export type InputSize = NonNullable<InputVariantConfig["size"]>;

export type InputVariantProps = StrictVariantProps<typeof inputVariants>;

// The bordered group that frames the input + its inline icon slots: the shared field-control
// surface (`focus: within`) + input geometry (radius/px per size), hover, transition,
// and the descendant-`:disabled` muting (disabled lives on the inner `<input>`). Danger isn't a
// prop — the surface recolors its border off the wrapped control's `data-invalid`.
// Height, text, glyph, gap and radius ride the rung tokens; the side inset rides the field inset
// ladder (`--field-inset-*`, two below the button inset at every rung).
export const inputGroupVariants = cva(cx(controlGroupClass, "w-full items-center"), {
  variants: {
    size: {
      md: cx(
        controlSize.md,
        "gap-(--control-gap-md) rounded-(--control-radius-md) px-(--field-inset-md)",
      ),
      lg: cx(
        controlSize.lg,
        "gap-(--control-gap-lg) rounded-(--control-radius-lg) px-(--field-inset-lg)",
      ),
      xl: cx(
        controlSize.xl,
        "gap-(--control-gap-xl) rounded-(--control-radius-xl) px-(--field-inset-xl)",
      ),
      "2xl": cx(
        controlSize["2xl"],
        "gap-(--control-gap-2xl) rounded-(--control-radius-2xl) px-(--field-inset-2xl)",
      ),
    },
  },
});

export type InputGroupVariantProps = StrictVariantProps<typeof inputGroupVariants>;
