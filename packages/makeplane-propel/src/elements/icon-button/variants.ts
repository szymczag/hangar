import { cva, type VariantProps } from "class-variance-authority";

import { composeVariants } from "../../internal/compose-variants";
import { controlChromeVariants } from "../../internal/control-chrome";
import { type StrictVariantProps } from "../../internal/variant-props";

// IconButton's local styling: the square geometry only. The chrome (behavior base + neutral/danger
// palette) comes from the shared `controlChromeVariants`. `variant` is declared (color-less) to
// keep the composed props pinned to the icon-button chrome set — no future shared-axis addition
// leaks in. Icon buttons are square: a fixed `size-N` box per Figma's "Icon button" Size scale
// (S/Base/L/XL = 20/24/28/32px → xs/sm/md/lg), each size setting `--node-size` to its rung's
// glyph (14/14/16/16px) for the glyph slot and spinner.
const iconButtonLocalVariants = cva("", {
  variants: {
    variant: {
      primary: "",
      secondary: "",
      tertiary: "",
      ghost: "",
      danger: "",
      "danger-outline": "",
    },
    size: {
      // 20px box, 14px glyph. The painted box stays at Figma's "S", but an icon-only control has
      // no label to widen it, so 20x20 is the one geometry here that can miss WCAG 2.2 SC 2.5.8's
      // 24x24 minimum on its own. A transparent 2px ring of `::before` brings the pointer target
      // to 24x24 without moving a pixel of the design. (`relative` comes from the shared chrome.)
      xs: "size-(--control-height-xs) rounded-(--control-radius-xs) [--node-size:var(--control-glyph-xs)] before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
      sm: "size-(--control-height-sm) rounded-(--control-radius-sm) [--node-size:var(--control-glyph-sm)]", // 24px box, 14px glyph
      md: "size-(--control-height-md) rounded-(--control-radius-md) [--node-size:var(--control-glyph-md)]", // 28px box, 16px glyph
      lg: "size-(--control-height-lg) rounded-(--control-radius-lg) [--node-size:var(--control-glyph-lg)]", // 32px box, 16px glyph
    },
  },
});

/** The full icon button className: the shared control chrome composed with the square geometry. */
export const iconButtonVariants = composeVariants(controlChromeVariants, iconButtonLocalVariants);

type IconButtonVariantConfig = VariantProps<typeof iconButtonLocalVariants>;
export type IconButtonVariant = NonNullable<IconButtonVariantConfig["variant"]>;
export type IconButtonSize = NonNullable<IconButtonVariantConfig["size"]>;

// Every axis stays required (no defaults); variant is the closed chrome set.
export type IconButtonVariantProps = StrictVariantProps<typeof iconButtonVariants>;
