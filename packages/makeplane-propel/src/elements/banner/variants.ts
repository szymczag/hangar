import { cva, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "../../internal/node-slot";
import { type StrictVariantProps } from "../../internal/variant-props";

// Size is independent of placement. Defaults to the medium Figma treatment.
const bannerDefaultVariants = { size: "md" } as const;
export const bannerVariants = cva(
  "relative flex flex-wrap items-center gap-2.5 overflow-clip after:pointer-events-none after:absolute after:inset-0 after:rounded-[inherit] after:border-inherit",
  {
    variants: {
      placement: { page: "after:border-b", inline: "rounded-lg after:border" },
      // The icon slot is one title line tall so the glyph centres on the first line. With no
      // title the first line is the (smaller) description, so the slot takes that leading instead.
      size: {
        sm: "px-3 py-2 [&:not(:has([data-slot=banner-title]))>[data-slot=banner-icon]]:leading-[18px]",
        md: "px-4 py-3 [&:not(:has([data-slot=banner-title]))>[data-slot=banner-icon]]:leading-5",
      },
      variant: { neutral: "", info: "", accent: "", warning: "", danger: "" },
    },
    compoundVariants: [
      { placement: "page", variant: "neutral", class: "border-subtle bg-surface-1" },
      { placement: "inline", variant: "neutral", class: "border-subtle bg-surface-2" },
      { variant: "info", class: "border-info-subtle bg-info-subtle" },
      { variant: "accent", class: "border-accent-subtle bg-accent-subtle" },
      { variant: "warning", class: "border-warning-subtle bg-warning-subtle" },
      { variant: "danger", class: "border-danger-subtle bg-danger-subtle" },
    ],
    defaultVariants: bannerDefaultVariants,
  },
);

// Align the glyph with the first text line, not the centre of a multiline message.
// Placement is retained for existing atomic compositions; it no longer changes glyph size.
const bannerIconDefaultVariants = { size: "md" } as const;
export const bannerIconVariants = cva([nodeSlotClass, "h-lh self-start"], {
  variants: {
    size: { sm: "text-body-xs-regular leading-5", md: "text-body-sm-regular leading-[22px]" },
    placement: { page: "", inline: "" },
    variant: {
      neutral: "text-icon-secondary [--node-size:var(--control-glyph-sm)]",
      info: "text-icon-info-secondary [--node-size:var(--control-glyph-lg)]",
      accent: "text-icon-accent-primary [--node-size:var(--control-glyph-lg)]",
      warning: "text-icon-warning-primary [--node-size:var(--control-glyph-lg)]",
      danger: "text-icon-danger-primary [--node-size:var(--control-glyph-lg)]",
    },
  },
  defaultVariants: bannerIconDefaultVariants,
});

const bannerBodyDefaultVariants = { size: "md" } as const;
export const bannerBodyVariants = cva("flex min-w-0 flex-1 basis-48 flex-col gap-0.5 break-words", {
  variants: {
    placement: { page: "", inline: "" },
    size: { sm: "text-body-xs-regular leading-5", md: "text-body-sm-regular leading-[22px]" },
    variant: {
      neutral: "text-secondary",
      info: "text-info-primary",
      accent: "text-accent-primary",
      warning: "text-warning-primary",
      danger: "text-danger-primary",
    },
  },
  defaultVariants: bannerBodyDefaultVariants,
});

const bannerTitleDefaultVariants = { size: "md" } as const;
export const bannerTitleVariants = cva("", {
  variants: {
    placement: { page: "", inline: "" },
    size: { sm: "text-body-xs-medium leading-5", md: "text-body-sm-medium leading-[22px]" },
  },
  defaultVariants: bannerTitleDefaultVariants,
});

// Semantic foreground still comes from BannerBody; leading is pinned to whole pixels like the title.
const bannerDescriptionDefaultVariants = { size: "md" } as const;
export const bannerDescriptionVariants = cva("", {
  variants: {
    size: { sm: "text-body-2xs-regular leading-[18px]", md: "text-body-xs-regular leading-5" },
  },
  defaultVariants: bannerDescriptionDefaultVariants,
});
export const bannerActionsVariants = cva(
  "flex max-w-full flex-wrap items-center gap-2 [&>*]:max-w-full [&>*]:min-w-0",
);

export type BannerPlacement = NonNullable<VariantProps<typeof bannerVariants>["placement"]>;
export type BannerVariant = NonNullable<VariantProps<typeof bannerVariants>["variant"]>;
export type BannerSize = NonNullable<VariantProps<typeof bannerVariants>["size"]>;
export type BannerVariantProps = StrictVariantProps<
  typeof bannerVariants,
  keyof typeof bannerDefaultVariants
>;
export type BannerBodyVariantProps = StrictVariantProps<
  typeof bannerBodyVariants,
  keyof typeof bannerBodyDefaultVariants
>;
export type BannerIconVariantProps = StrictVariantProps<
  typeof bannerIconVariants,
  keyof typeof bannerIconDefaultVariants
>;
export type BannerTitleVariantProps = StrictVariantProps<
  typeof bannerTitleVariants,
  keyof typeof bannerTitleDefaultVariants
>;
export type BannerDescriptionVariantProps = StrictVariantProps<
  typeof bannerDescriptionVariants,
  keyof typeof bannerDescriptionDefaultVariants
>;
