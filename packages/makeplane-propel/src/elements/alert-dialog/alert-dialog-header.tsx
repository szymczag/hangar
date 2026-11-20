import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { alertDialogHeaderVariants } from "./variants";

export type AlertDialogHeaderProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Groups the leading `AlertDialogIcon` badge above the `AlertDialogIntro` (title + description).
 * Lives inside `AlertDialogBody`. Pass icon and intro as children.
 */
export function AlertDialogHeader({ render, ...props }: AlertDialogHeaderProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: alertDialogHeaderVariants() };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
