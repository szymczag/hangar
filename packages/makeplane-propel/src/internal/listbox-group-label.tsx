import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva } from "class-variance-authority";

/**
 * The muted heading naming a group of listbox options, shared by the select, combobox and
 * autocomplete families (rule 4a). Matches the menu group label's type treatment so grouped pickers
 * and menus read the same. `text-caption-md-medium` (not a bare 12px + `font-medium` pair) so the
 * row picks up the preset's `1.2` line-height — the bare utility fell back to the browser's normal
 * (~1.5×) line-height, rendering the heading taller than the Figma "caption/md" spec.
 *
 * The heading is a flex row of two parts: a `ListboxGroupLabelTitle` holding the heading text and
 * an optional `ListboxGroupLabelMeta` pinned at the end. The text always sits inside the title,
 * never directly in the row — as direct flex children, mixed inline content (`Recent
 * <strong>files</strong>`) would split into separate flex items with the row's gap between them.
 * Each family grafts its Base UI `GroupLabel` onto the TITLE (`<BaseCombobox.GroupLabel
 * render={<ListboxGroupLabelTitle />} />`), so the group's accessible name is the heading text
 * alone, without the `meta` content.
 */
export const listboxGroupLabelVariants = cva(
  "flex items-center gap-1.5 px-2 py-1.5 text-caption-md-medium text-tertiary",
);

/**
 * The growing heading text. It wraps like the plain block heading it replaced, so a long Combobox
 * or Autocomplete heading keeps breaking onto a second line instead of truncating.
 */
export const listboxGroupLabelTitleVariants = cva("min-w-0 flex-1");

/** Content pinned at the heading's inline-end, e.g. a count or a "Clear" action. */
export const listboxGroupLabelMetaVariants = cva("shrink-0");

export type ListboxGroupLabelProps = Omit<useRender.ComponentProps<"div">, "className" | "style">;

export function ListboxGroupLabel({ render, ...props }: ListboxGroupLabelProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: listboxGroupLabelVariants(),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}

export type ListboxGroupLabelTitleProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

export function ListboxGroupLabelTitle({ render, ...props }: ListboxGroupLabelTitleProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: listboxGroupLabelTitleVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}

export type ListboxGroupLabelMetaProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

export function ListboxGroupLabelMeta({ render, ...props }: ListboxGroupLabelMetaProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: listboxGroupLabelMetaVariants(),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
