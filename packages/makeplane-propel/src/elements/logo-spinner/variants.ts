import { cva, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

/** The box that centres the brand loading mark in whatever space it is given. */
export const logoSpinnerVariants = cva("flex items-center justify-center");

// Rule 12: `motion` is the one axis with a sensible fallback — an image is the animated artwork
// unless it says it is the still — declared here so the props type stays in step with the cva.
const logoSpinnerImageDefaultVariants = { motion: "animated" } as const;

/**
 * One theme's brand mark, in one motion mode. `size` sets its height — `sm` 24px, `md` 44px,
 * `fluid` 24px stepping to 44px at the 640px breakpoint — and the width follows the artwork's
 * aspect ratio (`object-contain`, as the apps' own splash CSS did).
 *
 * `theme` is which theme's asset this is, and it is a real second axis rather than a look choice:
 * the mark is a raster pair, so the light/dark swap has to happen in CSS (`light` shows unless a
 * `dark` theme is active, mirroring the apps' `html[data-theme*="dark"]` rules). Doing it in CSS —
 * rather than picking one `src` from a theme hook — is what keeps the swap free of JS, of a
 * hydration flash, and of a second network request when the theme flips.
 *
 * `motion` is the third axis, for the same reason in the other direction: a GIF cannot be paused
 * from CSS, so a viewer who asked for reduced motion gets a still of the fully drawn mark instead.
 * `animated` paints under `prefers-reduced-motion: no-preference`, `still` under `reduce`, and the
 * four theme × motion combinations are exclusive — exactly one image paints — so `alt` is announced
 * once whatever the theme and the motion preference.
 *
 * Deliberately OFF the size ladder (`internal/size-scale`), like CircularProgress's ring diameters:
 * these are the product's two splash heights (24px inline, 44px full page), not control rungs.
 */
export const logoSpinnerImageVariants = cva("aspect-[79/44] w-auto shrink-0 object-contain", {
  variants: {
    // `fluid` is the product's own splash recipe: the small mark on a phone, stepping up at the
    // 640px breakpoint. It is a real third step rather than something a consumer can express
    // themselves, because propel parts take no `className`.
    size: { sm: "h-6", md: "h-11", fluid: "h-6 sm:h-11" },
    // Visibility is decided by the theme × motion pair below, never by one axis alone.
    theme: { light: "", dark: "" },
    motion: { animated: "", still: "" },
  },
  compoundVariants: [
    // Hidden by default; each pair paints only under its own media preference AND theme. The
    // stacked `motion-*:dark:` utilities sort after the single-variant ones, which is what lets
    // the dark rule win inside the same media query (propel's `dark` variant is `:where()`-scoped,
    // so it adds no specificity of its own).
    {
      theme: "light",
      motion: "animated",
      class: "hidden motion-safe:block motion-safe:dark:hidden",
    },
    { theme: "dark", motion: "animated", class: "hidden motion-safe:dark:block" },
    {
      theme: "light",
      motion: "still",
      class: "hidden motion-reduce:block motion-reduce:dark:hidden",
    },
    { theme: "dark", motion: "still", class: "hidden motion-reduce:dark:block" },
  ],
  defaultVariants: logoSpinnerImageDefaultVariants,
});

type LogoSpinnerImageVariantConfig = VariantProps<typeof logoSpinnerImageVariants>;
export type LogoSpinnerSize = NonNullable<LogoSpinnerImageVariantConfig["size"]>;
export type LogoSpinnerTheme = NonNullable<LogoSpinnerImageVariantConfig["theme"]>;
export type LogoSpinnerMotion = NonNullable<LogoSpinnerImageVariantConfig["motion"]>;

export type LogoSpinnerVariantProps = StrictVariantProps<typeof logoSpinnerVariants>;
export type LogoSpinnerImageVariantProps = StrictVariantProps<
  typeof logoSpinnerImageVariants,
  keyof typeof logoSpinnerImageDefaultVariants
>;
