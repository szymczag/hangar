import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  skeletonItemFrameProps,
  type SkeletonItemVariant,
  type SkeletonItemVariantProps,
} from "./variants";

export type { SkeletonItemVariant };

export type SkeletonItemProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style" | "width" | "height"
> &
  Omit<SkeletonItemVariantProps, "variant"> & {
    /**
     * Look of the bone: `bar` is a rounded-md block; `circle` is a disc.
     *
     * @default "bar"
     */
    variant?: SkeletonItemVariant;
    /**
     * CSS block-size (height) of the bone, e.g. `"50px"`, `"100%"`, or `"1rem"`. Omit to fill a
     * region that has a `blockSize`; in a region without one the bone is one text line tall (16px)
     * instead of collapsing. On `variant="circle"`, a lone `blockSize` is also applied as the
     * inline size (square).
     */
    blockSize?: string;
    /**
     * CSS inline-size (width) of the bone, e.g. `"70px"` or `"60%"`. Omit for the parent's full
     * inline size. On `variant="circle"`, a lone `inlineSize` is also applied as the block size
     * (square).
     */
    inlineSize?: string;
  };

/**
 * One styled placeholder bone. `variant="bar"` (default) is a rounded-md block; `variant="circle"`
 * is a disc. A bone is full width unless `inlineSize` narrows it. Exact lengths are applied as
 * `--skeleton-block-size` / `--skeleton-inline-size` so `style` is never exposed. Decorative —
 * `aria-hidden` is baked in; the region's `status` names it.
 */
export function SkeletonItem({
  variant = "bar",
  blockSize,
  inlineSize,
  render,
  ...props
}: SkeletonItemProps) {
  // A circle with only one length set is square — copy it onto the other axis rather than letting
  // the full-width default (or the `h-full` fallback) turn the disc into a pill.
  const isCircle = variant === "circle";
  const resolvedBlockSize = blockSize ?? (isCircle ? inlineSize : undefined);
  const resolvedInlineSize = inlineSize ?? (isCircle && blockSize != null ? blockSize : undefined);
  const defaultProps: useRender.ElementProps<"div"> = {
    "aria-hidden": true,
    ...skeletonItemFrameProps({
      variant,
      blockSize: resolvedBlockSize,
      inlineSize: resolvedInlineSize,
    }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
