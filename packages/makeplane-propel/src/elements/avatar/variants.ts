import { cva, type VariantProps } from "class-variance-authority";

import {
  avatarFallbackClass,
  avatarImageClass,
  avatarInitialsTextClass,
  avatarVariantClasses,
} from "../../internal/avatar-shared";
import { type StrictVariantProps } from "../../internal/variant-props";

export const avatarImageVariants = cva(avatarImageClass);

// The fallback's `variant` colors the initials surface — always one of the six Figma avatar label
// colors (initials on a solid variant, white text); there is no neutral "none" variant and no
// `defaultVariants`, so `variant` is required. The anonymous/icon state is not this part at all: when
// there are no initials, the ready-made renders the shared `Icon` directly instead of
// `AvatarFallback`. Exposing `variant` as a variant lets a composition (`components/avatar`) style the
// fallback without a `className`.
export const avatarFallbackVariants = cva(avatarFallbackClass, {
  variants: {
    variant: avatarVariantClasses,
  },
});

// Sizes follow the Figma "Avatar" component scale (px): 2xs 16 → 3xl 64.
// Border is 1px (`border-sm`) up to 32px and 2px (`border-lg`) from 40px up, in `border-subtle` —
// measured on the Figma render, which shows a 2px #eaebec ring on the standalone 56px avatar.
// Groups retain the same border-subtle ring; see elements/avatar-group/variants.
// `bg-layer-1` is the avatar's own neutral backdrop (shows behind a transparent fallback).
// `--node-size` is the anonymous icon glyph's size (Figma's explicit "icon" px, not a fixed
// fraction of the avatar); the fallback `<Icon>` inherits it from this root, so the icon is not a
// separate styled part.
// Unsized avatars land on 28px — the step that names the same height as the ladder's anchor
// rung, and what every unsized <Avatar> has always rendered.
const avatarDefaultVariants = {
  size: "md",
} as const;

export const avatarVariants = cva(
  "relative inline-flex shrink-0 items-center justify-center overflow-clip rounded-full border-subtle bg-layer-1",
  {
    variants: {
      size: {
        "2xs": `size-4 border-sm ${avatarInitialsTextClass["2xs"]} [--node-size:0.875rem]`, // 14px glyph
        xs: `size-5 border-sm ${avatarInitialsTextClass.xs} [--node-size:0.875rem]`, // 14px
        sm: `size-6 border-sm ${avatarInitialsTextClass.sm} [--node-size:1rem]`, // 16px
        md: `size-7 border-sm ${avatarInitialsTextClass.md} [--node-size:1.25rem]`, // 20px
        lg: `size-8 border-sm ${avatarInitialsTextClass.lg} [--node-size:1.5rem]`, // 24px
        xl: `size-10 border-lg ${avatarInitialsTextClass.xl} [--node-size:1.5rem]`, // 24px
        "2xl": `size-14 border-lg ${avatarInitialsTextClass["2xl"]} [--node-size:2rem]`, // 32px
        "3xl": `size-16 border-lg ${avatarInitialsTextClass["3xl"]} [--node-size:2rem]`, // 32px
      },
    },
    defaultVariants: avatarDefaultVariants,
  },
);

// Initials background utility per variant — the same palette as `avatarFallbackVariants`
// but exposed as a plain map for consumers (e.g. WorkspaceAvatar) that style their own
// fallback surface without using `AvatarFallback`. All className decisions live here in
// variants.ts, not scattered across component files.
export const avatarVariantBgClass = {
  orange: "bg-label-orange-bg-strong",
  indigo: "bg-label-indigo-bg-strong",
  emerald: "bg-label-emerald-bg-strong",
  crimson: "bg-label-crimson-bg-strong",
  pink: "bg-label-pink-bg-strong",
  purple: "bg-label-purple-bg-strong",
} as const;

type AvatarVariantConfig = VariantProps<typeof avatarVariants>;
export type AvatarSize = NonNullable<AvatarVariantConfig["size"]>;
export type AvatarVariantProps = StrictVariantProps<
  typeof avatarVariants,
  keyof typeof avatarDefaultVariants
>;

export type AvatarFallbackVariant = NonNullable<
  VariantProps<typeof avatarFallbackVariants>["variant"]
>;
export type AvatarFallbackVariantProps = StrictVariantProps<typeof avatarFallbackVariants>;
