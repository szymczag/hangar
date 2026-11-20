import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { LIST_ITEM_PRIMARY_ATTR } from "../../internal/list-item-primary";
import { listItemLinkVariants } from "./variants";

export type ListItemLinkProps = Omit<useRender.ComponentProps<"a">, "className" | "style">;

/**
 * The styled primary navigation target of a list row — an `<a>`. Base-UI-agnostic — graft the
 * roving `CompositeItem` behavior in `components` via `<CompositeItem tag="a"
 * render={<ListItemLink/>} />`. Mark the current page with `aria-current="page"` (the wrapping
 * `ListItem` reads it for the selected look). Compose a leading `<Icon />`, `ListItemLabel`, and
 * optional `ListItemCounter` / trailing icon inside.
 */
export function ListItemLink({ render, ...props }: ListItemLinkProps) {
  const defaultProps: useRender.ElementProps<"a"> & { [LIST_ITEM_PRIMARY_ATTR]: "" } = {
    [LIST_ITEM_PRIMARY_ATTR]: "",
    className: listItemLinkVariants(),
  };
  return useRender({ defaultTagName: "a", render, props: mergeProps(defaultProps, props) });
}
