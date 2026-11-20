import {
  Skeleton as SkeletonElement,
  type SkeletonLayout,
  type SkeletonProps as SkeletonElementProps,
  type SkeletonStretch,
} from "../../elements/skeleton";

export type { SkeletonLayout, SkeletonStretch };

export type SkeletonProps = Omit<
  SkeletonElementProps,
  "aria-label" | "role" | "layout" | "stretch" | "blockSize" | "inlineSize"
> & {
  /**
   * Arrangement of bones: `stack` is a column, `row` is a row.
   *
   * @default "stack"
   */
  layout?: SkeletonLayout;
  /**
   * `full` takes the parent's inline size; `auto` is fit-content — the region shrinks to the widest
   * bone that carries an `inlineSize`. A passed `inlineSize` overrides both.
   *
   * @default "full"
   */
  stretch?: SkeletonStretch;
  /**
   * CSS block-size (height) of the loading region, e.g. `"10rem"` or `"160px"`. Omit to size to the
   * bones inside.
   */
  blockSize?: string;
  /**
   * CSS inline-size (width) of the loading region, e.g. `"8rem"`. Omit to follow `stretch`. Passing
   * a length overrides `stretch`.
   */
  inlineSize?: string;
  /** Accessible name for the loading region. */
  "aria-label": string;
};

/**
 * A pulse-animated loading region that groups placeholder bones. Grafts `role="status"` onto the
 * styled `elements` `Skeleton` and requires an `aria-label` so the region is never unnamed. Compose
 * `SkeletonItem` children for the bones.
 *
 * `layout` and `stretch` own the region's flex axis and inline size. Exact geometry uses
 * `blockSize` / `inlineSize` (not `height` / `width`).
 */
export function Skeleton(props: SkeletonProps) {
  return <SkeletonElement role="status" {...props} />;
}
