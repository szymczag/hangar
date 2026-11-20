import {
  SelectStickyList as SelectStickyListElement,
  type SelectStickyListProps as SelectStickyListElementProps,
} from "../../elements/select";

export type SelectStickyListProps = SelectStickyListElementProps;

/**
 * Pads sticky rows in `SelectContent`'s `header` (a `SelectSelectAll` + `SelectSeparator`) with the
 * same inset the scrolling list uses.
 */
export function SelectStickyList(props: SelectStickyListProps) {
  return <SelectStickyListElement {...props} />;
}
