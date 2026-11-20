import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type SplitButtonVariantProps, splitButtonVariants } from "./variants";

export type { SplitButtonSize, SplitButtonVariant } from "./variants";

export type SplitButtonProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  SplitButtonVariantProps;

/**
 * The styled frame around a split button's two segments — the main action button and the
 * menu-opening icon button. Both variants flatten the segments' facing corners and keep their outer
 * `rounded-md`; what differs is the seam. Primary holds the two pills 1px apart, secondary
 * collapses the shared border so they read as one connected outline with a divider. Neutral only —
 * there is no danger/error split button. The segments keep their own control chrome.
 * Base-UI-agnostic (there is no Base UI split-button primitive); the `components` ready-made
 * composes `Button` + `MenuTrigger`-grafted `IconButton` inside it.
 */
export function SplitButton({ variant, size, render, ...props }: SplitButtonProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: splitButtonVariants({ variant, size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
