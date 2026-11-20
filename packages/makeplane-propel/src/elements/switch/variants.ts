import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// Sizes follow the Figma "Toggle" Size scale (track w×h, px):
//   L 30×18 → lg · M 27×16 → md · S 23×14 → sm.
// The thumb is the track height minus a 1px gap top/bottom; on/off it travels
// from the 1px gutter on one side to the 1px gutter on the other.
//
// `size` lives on the track only. Each size publishes the thumb's
// diameter and checked-state travel as CSS variables (`--switch-thumb-size`,
// `--switch-thumb-travel`); the thumb reads them off its parent track rather
// than taking its own size prop — the node-slot philosophy applied to the knob,
// so the track stays the single source of the size axis.
export const switchVariants = cva(
  cx(
    // `duration-100`, matching Checkbox/Radio: one snappy fill speed across every small toggle
    // control. The thumb's slide (`switchThumbVariants`) matches too, so the track's color change
    // and the knob's travel finish together instead of the fill completing before the slide.
    "relative inline-flex shrink-0 cursor-pointer items-center rounded-full p-px transition-colors duration-100",
    // Every track height sits under WCAG 2.2 SC 2.5.8's 24×24 pointer-target minimum. A transparent
    // `::before` ring closes the gap per size, same technique as IconButton's `xs` and Pill's
    // compact size — the painted track doesn't move a pixel.
    "before:absolute before:content-['']",
    // Off track = Figma icon/placeholder; on track = accent/primary.
    "bg-icon-placeholder data-checked:bg-accent-primary",
    // Unchangeable (disabled or readonly) dims to 40%, matching Figma's "Unchangeable" states —
    // except disabled+off, which Figma paints solid with the icon/disabled swatch (`#71777A`)
    // instead of fading `icon/placeholder` (too light at 40%). That hex is `--txt-disabled` here —
    // same token Checkbox uses (`internal/checkbox-box.ts`); do not remap via `--txt-icon-disabled`.
    // Disabled also blocks the cursor; readonly keeps the default arrow (dims only, no cursor change).
    "data-disabled:cursor-not-allowed data-disabled:not-data-checked:bg-(--txt-disabled) data-disabled:data-checked:opacity-40 data-readonly:cursor-default data-readonly:opacity-40",
    // `outline-none` clears the UA focus outline so it doesn't stack with the ring (Radio/Checkbox
    // do the same). `focus-visible:outline-2 outline-transparent` keeps a forced-colors/WHCM
    // indicator once the ring's box-shadow is stripped — transparent ink is replaced by the system
    // highlight color under Windows High Contrast.
    "outline-none focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-2 focus-visible:outline-2 focus-visible:outline-transparent",
    // `Field.Root` propagates `data-invalid` here the same way it does to Checkbox. Scoped to
    // `not-data-checked`, matching Checkbox's rule (internal/checkbox-box.ts): a checked switch the
    // user already turned on shouldn't keep reading as an error once it reflects a valid choice, and
    // the exclusion also sidesteps the same cascade-ordering pitfall Checkbox's comment documents.
    "data-invalid:not-data-checked:shadow-[inset_0_0_0_1px_var(--border-color-danger-strong)]",
  ),
  {
    variants: {
      size: {
        // A `::before` with only a vertical inset never gets a horizontal anchor, so its width
        // shrink-to-fits to 0 and it contributes no hit area at all — `inset-x` must be set
        // explicitly on every size (even to `0`, pinning it to the track's own edges) for the
        // ring to actually cover anything. `lg`/`md`'s width already clears 24px, so `inset-x-0`
        // is enough; `sm` needs a sliver of real horizontal expansion too.
        lg: "h-[18px] w-[30px] [--switch-thumb-size:1rem] [--switch-thumb-travel:12px] before:inset-x-0 before:-inset-y-[3px]",
        md: "h-4 w-[27px] [--switch-thumb-size:0.875rem] [--switch-thumb-travel:11px] before:inset-x-0 before:-inset-y-1",
        sm: "h-[14px] w-[23px] [--switch-thumb-size:0.75rem] [--switch-thumb-travel:9px] before:-inset-x-px before:-inset-y-[5px]",
      },
    },
  },
);

// The sliding knob. Its diameter (track height − 2px gap) and checked-state
// travel (track width − thumb − 2px of gutters) both come from the track's
// per-size CSS variables, so the thumb has no size axis of its own.
// In RTL the thumb travels toward the inline-start edge, so the translate is
// negated. The thumb stays white in every theme and in both on/off states:
// `on-color` is the white-on-variant token, which holds across the theme flip.
export const switchThumbVariants = cva(
  cx(
    "size-(--switch-thumb-size) rounded-full bg-on-color shadow-raised-100 transition-transform duration-100",
    "data-checked:translate-x-(--switch-thumb-travel)",
    "rtl:data-checked:-translate-x-(--switch-thumb-travel)",
  ),
);

export type SwitchSize = NonNullable<VariantProps<typeof switchVariants>["size"]>;
export type SwitchVariantProps = StrictVariantProps<typeof switchVariants>;
