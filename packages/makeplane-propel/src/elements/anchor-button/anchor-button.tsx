import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type AnchorButtonVariantProps, anchorButtonVariants } from "./variants";

export type { AnchorButtonSize, AnchorButtonVariant } from "./variants";

export type AnchorButtonProps = Omit<useRender.ComponentProps<"a">, "className" | "style"> &
  AnchorButtonVariantProps;

/**
 * The styled intrinsic anchor for the inline text-link look. Selects link palette (`variant`) and
 * text size (`size`). Use `render` to project its props onto a router or framework link. For a
 * lightweight text-only action, use `TextButton`; for a navigation link wearing button chrome, use
 * `Button`'s render path. Does not accept `className` or `style`.
 */
export function AnchorButton({ variant, size, render, ...props }: AnchorButtonProps) {
  const defaultProps: useRender.ElementProps<"a"> = {
    className: anchorButtonVariants({ variant, size }),
  };
  return useRender({ defaultTagName: "a", render, props: mergeProps(defaultProps, props) });
}
