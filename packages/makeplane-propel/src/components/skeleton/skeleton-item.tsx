import {
  SkeletonItem as SkeletonItemElement,
  type SkeletonItemProps as SkeletonItemElementProps,
  type SkeletonItemVariant,
} from "../../elements/skeleton";

export type { SkeletonItemVariant };

export type SkeletonItemProps = Omit<
  SkeletonItemElementProps,
  "variant" | "blockSize" | "inlineSize" | "aria-hidden"
> & {
  /**
   * Look of the bone: `bar` is a rounded-md block; `circle` is a disc.
   *
   * @default "bar"
   */
  variant?: SkeletonItemVariant;
  /**
   * CSS block-size (height) of the bone, e.g. `"50px"`, `"100%"`, or `"1rem"`. Omit to fill a
   * region that has a `blockSize`; in a region without one the bone is one text line tall (16px).
   * On `variant="circle"`, a lone `blockSize` is also the inline size (square).
   */
  blockSize?: string;
  /**
   * CSS inline-size (width) of the bone, e.g. `"70px"` or `"60%"`. Omit for the parent's full
   * inline size.
   */
  inlineSize?: string;
};

/**
 * One decorative placeholder bone. `variant="bar"` (default) is a rounded-md block;
 * `variant="circle"` is a disc. Full width unless `inlineSize` narrows it. Bakes `aria-hidden` —
 * the enclosing `Skeleton` names the loading region.
 */
export function SkeletonItem(props: SkeletonItemProps) {
  return <SkeletonItemElement aria-hidden {...props} />;
}
