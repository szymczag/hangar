import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type AlertDialogActionsVariantProps, alertDialogActionsVariants } from "./variants";

export type { AlertDialogActionsLayout } from "./variants";
export type AlertDialogActionsProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  AlertDialogActionsVariantProps;

/**
 * The footer row of action buttons. Sits flush under the body with no divider, pads 12px on top and
 * 20px on the sides and bottom (Figma), and end-aligns children with a 12px gap. Below 640px,
 * actions form a reversed full-width column, retaining the legacy mobile order.
 *
 * Layout groups actions at the end, or separates a leading action from an action group.
 *
 * @default "inline"
 */
export function AlertDialogActions({ layout, render, ...props }: AlertDialogActionsProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: alertDialogActionsVariants({ layout }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
