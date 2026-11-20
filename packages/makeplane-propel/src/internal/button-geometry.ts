import { cva, cx, type VariantProps } from "class-variance-authority";

// The label-button geometry for surfaces that wear control chrome with a text label: `Button`.
// Owns the label row (gap/font), the per-size height/min-width/padding/text + `--node-size`
// glyph scale (Figma "Buttons" Size), and full-width `stretch`. Compose with
// `controlChromeVariants` via `composeVariants`. (The inline text-link look is
// `linkChromeVariants` on `AnchorButton` — not this geometry.)
// Every geometry axis rides the rung tokens (`--control-*`, styles/variables.css): height,
// side padding (= (h − 8) / 2, so density climbs with size instead of flattening), the
// icon-to-label gap (follows the glyph: 4px beside 14px, 6px beside 16px), the glyph itself
// (paired to that gap), and the corner radius (4px at 20px, 6px above). Only `min-w` is local.
export const buttonGeometryVariants = cva(cx("whitespace-nowrap"), {
  variants: {
    size: {
      // 20px painted, 24px pointer target via a transparent `::before` ring (the chrome base
      // is already `relative`) — WCAG 2.5.8's floor, same mechanism as IconButton's 20px step.
      // `-z-10` layers the invisible ring beneath adjacent static siblings so its 2px overhang
      // never captures their edge clicks; it still catches pointers over empty gaps.
      xs: cx(
        "h-(--control-height-xs) min-w-10 gap-(--control-gap-xs) px-(--control-padding-x-xs)",
        "rounded-(--control-radius-xs) text-caption-md-medium [--node-size:var(--control-glyph-xs)]",
        "before:absolute before:-inset-0.5 before:-z-10 before:content-['']",
      ),
      sm: cx(
        "h-(--control-height-sm) min-w-10 gap-(--control-gap-sm) px-(--control-padding-x-sm)",
        "rounded-(--control-radius-sm) text-body-xs-medium [--node-size:var(--control-glyph-sm)]",
      ),
      md: cx(
        "h-(--control-height-md) min-w-12 gap-(--control-gap-md) px-(--control-padding-x-md)",
        "rounded-(--control-radius-md) text-body-xs-medium [--node-size:var(--control-glyph-md)]",
      ),
      lg: cx(
        "h-(--control-height-lg) min-w-13 gap-(--control-gap-lg) px-(--control-padding-x-lg)",
        "rounded-(--control-radius-lg) text-body-sm-medium [--node-size:var(--control-glyph-lg)]",
      ),
    },
    stretch: { auto: "", full: "w-full" },
  },
});

export type ButtonGeometryVariantProps = VariantProps<typeof buttonGeometryVariants>;
