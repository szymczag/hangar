import {
  ComboboxStickyList as ComboboxStickyListElement,
  type ComboboxStickyListProps as ComboboxStickyListElementProps,
} from "../../elements/combobox";

export type ComboboxStickyListProps = ComboboxStickyListElementProps;

/** Pads sticky header rows (Select all + separator) with the same inset the scrolling list uses. */
export function ComboboxStickyList(props: ComboboxStickyListProps) {
  return <ComboboxStickyListElement {...props} />;
}
