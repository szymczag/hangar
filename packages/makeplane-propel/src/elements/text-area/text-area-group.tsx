import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type TextAreaGroupVariantProps,
  type TextAreaResize,
  textAreaGroupVariants,
} from "./variants";

export type { TextAreaResize };

export type TextAreaGroupProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  TextAreaGroupVariantProps;

/**
 * The bordered frame that wraps a `field`-surface `TextArea` leaf. Owns the border, radius,
 * focus/error border treatments, and the native `resize` handle so growth carries the chrome with
 * the content. Children should be that single leaf only — the field surface is `min-w-full`, so a
 * sibling inside the frame overflows. Put attach/submit controls outside the group, or use the
 * `embedded` / `inline` surfaces (no group) for composer rows. Pair `autoResize` on the leaf with
 * `resize="none"` so the native drag handle does not fight content-driven height.
 *
 * @default resize = "vertical"
 */
export function TextAreaGroup({ resize, render, ...props }: TextAreaGroupProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: textAreaGroupVariants({ resize }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
