import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogIntroVariants } from "./variants";

export type AlertDialogIntroProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Groups the title and description with a 6px gap. Pass `AlertDialogTitle` and
 * `AlertDialogDescription` as children.
 */
export function AlertDialogIntro({ render, ...props }: AlertDialogIntroProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: alertDialogIntroVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
