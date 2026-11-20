import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { drawerInlineHostVariants } from "./variants";

export type DrawerInlineHostProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

/**
 * Absolute-fill portal host for inline drawers when no `container` is passed. The parent must be
 * positioned (`relative`). Used by `DrawerPanel` for `variant="inline"`.
 */
export function DrawerInlineHost({ render, ...props }: DrawerInlineHostProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: drawerInlineHostVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
