import { cva, cx, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { type StrictVariantProps } from "../../internal/variant-props";

const skeletonDefaultVariants = { layout: "stack" } as const;

/**
 * The loading-region frame: pulse lives here so every bone animates together. `layout` is the flex
 * axis (`stack` / `row`). Inline size is not a cva axis — see `skeletonFrameProps`: exactly one
 * width utility is emitted per part, chosen from `stretch` and `inlineSize`, so a fit-content
 * region and an explicit length can never fight over the same property.
 */
export const skeletonVariants = cva("animate-pulse motion-reduce:animate-none", {
  variants: {
    layout: {
      stack: "flex flex-col gap-2",
      row: "flex flex-row gap-2",
    },
  },
  defaultVariants: skeletonDefaultVariants,
});

const skeletonItemDefaultVariants = { variant: "bar" } as const;

/**
 * One decorative bone. `variant` is the look (`bar` has rounded-md corners; `circle` is a disc).
 * Height is not an axis — `blockSize` lands as a CSS variable. Omitting it fills a sized region
 * (`h-full`) and, in an unsized one, keeps the bone one text line tall (`min-h-4`) rather than
 * collapsing to nothing.
 */
export const skeletonItemVariants = cva("bg-layer-1", {
  variants: {
    variant: {
      bar: "rounded-md",
      circle: "shrink-0 rounded-full",
    },
  },
  defaultVariants: skeletonItemDefaultVariants,
});

/**
 * Full vs fit-content inline size of the region. Not a cva axis (see `skeletonFrameProps`), so the
 * union is declared here and stays the public per-axis type.
 */
export type SkeletonStretch = "auto" | "full";

type SkeletonVariantConfig = VariantProps<typeof skeletonVariants>;
export type SkeletonLayout = NonNullable<SkeletonVariantConfig["layout"]>;
export type SkeletonVariantProps = StrictVariantProps<
  typeof skeletonVariants,
  keyof typeof skeletonDefaultVariants
>;

type SkeletonItemVariantConfig = VariantProps<typeof skeletonItemVariants>;
export type SkeletonItemVariant = NonNullable<SkeletonItemVariantConfig["variant"]>;
export type SkeletonItemVariantProps = StrictVariantProps<
  typeof skeletonItemVariants,
  keyof typeof skeletonItemDefaultVariants
>;

/**
 * Turns the size inputs into the `--skeleton-*-size` CSS vars plus the matching `h-` / `w-`
 * utilities, layered onto a base class. Width is decided once, in priority order: an explicit
 * `inlineSize` wins, then `stretch` picks `w-full` or `w-fit` — never two width utilities on one
 * element, so the result does not depend on stylesheet order. `blockFallbackClassName` covers the
 * "no exact block length" case, which differs per part.
 */
function withSize(
  baseClassName: string,
  size: { blockSize?: string; inlineSize?: string; stretch: SkeletonStretch },
  blockFallbackClassName?: string,
) {
  const { blockSize, inlineSize, stretch } = size;
  return {
    className: cx(
      baseClassName,
      blockSize != null ? "h-(--skeleton-block-size)" : blockFallbackClassName,
      inlineSize != null ? "w-(--skeleton-inline-size)" : stretch === "full" ? "w-full" : "w-fit",
    ),
    style: {
      ...(blockSize != null ? { "--skeleton-block-size": blockSize } : {}),
      ...(inlineSize != null ? { "--skeleton-inline-size": inlineSize } : {}),
    } as React.CSSProperties,
  };
}

export function skeletonFrameProps(props: {
  layout: SkeletonLayout;
  stretch: SkeletonStretch;
  blockSize?: string;
  inlineSize?: string;
}) {
  return withSize(skeletonVariants({ layout: props.layout }), {
    blockSize: props.blockSize,
    inlineSize: props.inlineSize,
    stretch: props.stretch,
  });
}

export function skeletonItemFrameProps(props: {
  variant: SkeletonItemVariant;
  blockSize?: string;
  inlineSize?: string;
}) {
  // A bone has no `stretch` of its own: it is full width unless an `inlineSize` narrows it — the
  // only way a bone ever ended up narrower — so the axis would have been a no-op and is derived.
  return withSize(
    skeletonItemVariants({ variant: props.variant }),
    { blockSize: props.blockSize, inlineSize: props.inlineSize, stretch: "full" },
    "h-full min-h-4",
  );
}
