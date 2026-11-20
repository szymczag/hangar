import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { drawerHeaderVariants } from "./variants";

export type DrawerHeaderProps = Omit<useRender.ComponentProps<"header">, "className" | "style">;

/**
 * The drawer's top region (the Figma header). Compose a start cluster (`DrawerHeaderStart` or
 * `DrawerHeaderActions side="start"`) and an end cluster (`DrawerHeaderActions side="end"`) for the
 * title/icon sockets.
 */
export function DrawerHeader({ render, ...props }: DrawerHeaderProps) {
  const defaultProps: useRender.ElementProps<"header"> = { className: drawerHeaderVariants() };
  return useRender({ defaultTagName: "header", render, props: mergeProps(defaultProps, props) });
}
