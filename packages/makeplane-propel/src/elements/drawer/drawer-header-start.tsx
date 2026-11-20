import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { drawerHeaderStartVariants } from "./variants";

export type DrawerHeaderStartProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * The header's inline-start title cluster (Figma narrow header). Holds an optional
 * `DrawerHeaderIcon` / `IconButton` plus `DrawerHeaderContent` (title + description).
 */
export function DrawerHeaderStart({ render, ...props }: DrawerHeaderStartProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerHeaderStartVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
