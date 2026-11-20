import { Autocomplete as BaseAutocomplete } from "@base-ui/react/autocomplete";

import { ListboxItem, type ListboxItemSize } from "../../internal/listbox-item";

export type AutocompleteItemProps = Omit<
  BaseAutocomplete.Item.Props,
  "className" | "style" | "render"
> & {
  /** Visual size of the row: height and text size. Required. */
  size: ListboxItemSize;
};

/**
 * The ready-made autocomplete option row: grafts Base UI's `Autocomplete.Item` behavior onto the
 * shared listbox row (autocomplete rows carry no selection marker). Children flow through as the
 * row's content.
 */
export function AutocompleteItem({ size, ...props }: AutocompleteItemProps) {
  return <BaseAutocomplete.Item {...props} render={<ListboxItem size={size} />} />;
}
