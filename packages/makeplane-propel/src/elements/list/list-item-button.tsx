import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { LIST_ITEM_PRIMARY_ATTR } from "../../internal/list-item-primary";
import { listItemButtonVariants } from "./variants";

export type ListItemButtonProps = Omit<useRender.ComponentProps<"button">, "className" | "style">;

/**
 * The styled primary action of a list row — a `<button>`. Base-UI-agnostic — graft the roving
 * `CompositeItem` behavior in `components` via `<CompositeItem tag="button"
 * render={<ListItemButton/>} />`. Shares the row chrome with `ListItemLink`. Compose a leading
 * `<Icon />`, `ListItemLabel`, and optional `ListItemCounter` / trailing icon inside.
 */
export function ListItemButton({ render, ...props }: ListItemButtonProps) {
  const defaultProps: useRender.ElementProps<"button"> & { [LIST_ITEM_PRIMARY_ATTR]: "" } = {
    type: "button",
    [LIST_ITEM_PRIMARY_ATTR]: "",
    className: listItemButtonVariants(),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
