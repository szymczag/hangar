import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// Badge is the small rounded pill of inline text (a status tag, a "Paid"/"Free"
// label). Per the designer spec on the Badge issue, every part's static chrome lives
// in cva here so each part stays a single styled element with no `className` at the
// boundary.
//
// "Always the same" (baked into the base of `badgeVariants`):
//   inline-flex with centered content, single-line text (whitespace-nowrap), the medium
//   weight and line-height carried by the per-size text token, and `align-middle` — an
//   inline-flex box in inline flow otherwise sits on its first item's baseline, so a badge
//   after a heading's text would ride up with whatever leads it (same reasoning as Pill).
//
// "Depends (adjustable)" — exposed as required cva variants:
//   - size: Figma xs / sm / md → 20 / 24 / 28px
//   - variant: color/sentiment (neutral, grey, brand, …)
export const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center align-middle whitespace-nowrap",
  {
    variants: {
      // Height/gap/glyph/corner ride the compact ladder. Side padding is badge-owned
      // (6 / 6 / 8 — tighter than button sides from sm up); `md` label is body-sm, not
      // the rung's body-xs. Measurement history lives in `internal/size-scale.ts`.
      size: {
        xs: cx(
          "h-(--control-height-xs) gap-(--control-gap-xs) px-(--control-padding-x-xs)",
          "rounded-(--control-radius-xs) text-caption-md-medium [--node-size:var(--control-glyph-xs)]",
        ),
        sm: cx(
          "h-(--control-height-sm) gap-(--control-gap-sm) px-1.5",
          "rounded-(--control-radius-sm) text-body-xs-medium [--node-size:var(--control-glyph-sm)]",
        ),
        md: cx(
          "h-(--control-height-md) gap-(--control-gap-md) px-2",
          "rounded-(--control-radius-md) text-body-sm-medium [--node-size:var(--control-glyph-md)]",
        ),
      },
      // Figma Color/sentiment axis (`danger` = Figma's "Error"). Label-hue variants map to
      // `bg-label-*`/`text-label-*` utilities; semantic variants (brand/info/success/warning/danger)
      // map to the matching subtle background + primary text tokens — no arbitrary hex. `info`
      // is not in the Figma badges set but stays: it is the library-wide semantic vocabulary
      // (Banner and Toast carry it too), and `purple` is the set's decorative hue beside it.
      variant: {
        // Figma neutral: `background/layer/3` fill with `text/secondary` (not the grey label text —
        // that is what tells `neutral` and `grey` apart).
        neutral: "bg-layer-3 text-secondary",
        grey: "bg-label-grey-bg text-label-grey-text",
        brand: "bg-accent-subtle text-accent-primary",
        info: "bg-info-subtle text-info-primary",
        purple: "bg-label-purple-bg text-label-purple-text",
        indigo: "bg-label-indigo-bg text-label-indigo-text",
        success: "bg-success-subtle text-success-primary",
        emerald: "bg-label-emerald-bg text-label-emerald-text",
        warning: "bg-warning-subtle text-warning-primary",
        yellow: "bg-label-yellow-bg text-label-yellow-text",
        danger: "bg-danger-subtle text-danger-primary",
        crimson: "bg-label-crimson-bg text-label-crimson-text",
        orange: "bg-label-orange-bg text-label-orange-text",
      },
    },
  },
);

type BadgeVariantConfig = VariantProps<typeof badgeVariants>;
export type BadgeSize = NonNullable<BadgeVariantConfig["size"]>;
export type BadgeVariant = NonNullable<BadgeVariantConfig["variant"]>;
export type BadgeVariantProps = StrictVariantProps<typeof badgeVariants>;

// The badge's text label. Single-line (the base already sets `whitespace-nowrap`); kept
// as its own region so the label and leading/trailing icons compose as siblings.
export const badgeLabelVariants = cva("min-w-0");
