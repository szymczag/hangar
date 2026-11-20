import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  type ListItemDensity,
  type ListItemLevel,
  type ListItemVariantProps,
  listItemVariants,
} from "./variants";

export type { ListItemDensity, ListItemLevel } from "./variants";

export type ListItemProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  Omit<ListItemVariantProps, "level" | "density"> & {
    /**
     * Nesting depth — steps the row's left inset by 8px per level (1–5).
     *
     * @default 1
     */
    level?: ListItemLevel;
    /**
     * Label/counter text density. Row height and icon size stay fixed at both values (`comfortable`
     * = 14px, `compact` = 13px). Not a ladder `size` — height is always 32px.
     *
     * @default "comfortable"
     */
    density?: ListItemDensity;
  };

/**
 * A row wrapper. Holds a primary `ListItemLink` (or `ListItemButton`) plus optional actions or a
 * count as siblings, and carries the row chrome. `level` indents nested rows; `density` sets the
 * label/counter text scale. Renders a `<div>` by default.
 */
export function ListItem({ render, level, density, ...props }: ListItemProps) {
  return useRender({
    defaultTagName: "div",
    render,
    props: mergeProps({ className: listItemVariants({ level, density }) }, props),
  });
}
