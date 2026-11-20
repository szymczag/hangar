import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  skeletonFrameProps,
  type SkeletonLayout,
  type SkeletonStretch,
  type SkeletonVariantProps,
} from "./variants";

export type { SkeletonLayout, SkeletonStretch };

export type SkeletonProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style" | "width" | "height"
> &
  Omit<SkeletonVariantProps, "layout"> & {
    /**
     * Arrangement of bones: `stack` is a column, `row` is a row.
     *
     * @default "stack"
     */
    layout?: SkeletonLayout;
    /**
     * `full` takes the parent's inline size; `auto` is fit-content — the region shrinks to the
     * widest bone that carries an `inlineSize` (a bone without one is full width, so it has no
     * width of its own to shrink to). A passed `inlineSize` overrides both.
     *
     * @default "full"
     */
    stretch?: SkeletonStretch;
    /**
     * CSS block-size (height) of the loading region, e.g. `"10rem"` or `"160px"`. Omit to size to
     * the bones inside.
     */
    blockSize?: string;
    /**
     * CSS inline-size (width) of the loading region, e.g. `"8rem"`. Omit to follow `stretch`.
     * Passing a length overrides `stretch`.
     */
    inlineSize?: string;
  };

/**
 * The styled loading-region frame — pulse, layout, and optional exact geometry. Base-UI-agnostic;
 * the `status` role and required name are wired in `components`. Exact lengths are applied as
 * `--skeleton-block-size` / `--skeleton-inline-size` so `style` is never exposed.
 */
export function Skeleton({
  layout = "stack",
  stretch = "full",
  blockSize,
  inlineSize,
  render,
  ...props
}: SkeletonProps) {
  const defaultProps: useRender.ElementProps<"div"> = skeletonFrameProps({
    layout,
    stretch,
    blockSize,
    inlineSize,
  });
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
