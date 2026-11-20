import { cva } from "class-variance-authority";

import { type StrictVariantProps } from "../../internal/variant-props";

// Overlapping stack of avatars — mirrors the Figma "Avatar groups" -6px overlap.
// Members retain their standalone border-subtle ring, matching Figma set 1112:180.
export const avatarGroupVariants = cva("inline-flex items-center -space-x-1.5");

const avatarGroupCounterDefaultVariants = { size: "xs" } as const;

// Fixed orange initials avatar per the Figma instance (1112:180), with 9/9/11px counter text.
export const avatarGroupCounterVariants = cva(
  "relative inline-flex shrink-0 items-center justify-center overflow-clip rounded-full border-subtle bg-label-orange-bg-strong text-on-color",
  {
    variants: {
      size: {
        "2xs": "size-4 border-sm text-caption-2xs-regular",
        xs: "size-5 border-sm text-caption-2xs-regular",
        sm: "size-6 border-sm text-caption-sm-regular",
      },
    },
    defaultVariants: avatarGroupCounterDefaultVariants,
  },
);

export type AvatarGroupCounterVariantProps = StrictVariantProps<
  typeof avatarGroupCounterVariants,
  keyof typeof avatarGroupCounterDefaultVariants
>;

// The tooltip trigger owns focus outside the clipped counter art. Its transparent hit area grows
// to 24px without changing the Figma counter size or the stack's overlap.
export const avatarGroupOverflowVariants = cva(
  "relative inline-flex shrink-0 items-center justify-center rounded-full outline-none before:absolute before:inset-s-0 before:top-1/2 before:size-[max(24px,100%)] before:-translate-y-1/2 before:rounded-full focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:ring-offset-1",
);
