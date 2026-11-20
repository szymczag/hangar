import { Combobox as BaseCombobox } from "@base-ui/react/combobox";

import {
  ComboboxSearch as ComboboxSearchElement,
  ComboboxSearchInput,
} from "../../elements/combobox";
import { SearchOutline } from "../../icons";
import { Icon } from "../../internal/icon";

export type ComboboxSearchProps = Omit<
  BaseCombobox.Input.Props,
  "className" | "style" | "render"
> & {
  /** Placeholder text. @default "Search" */
  placeholder?: string;
  /**
   * Accessible name for the search combobox. Placeholder is not a name — override to localize, or
   * pass `aria-labelledby` instead.
   *
   * @default "Search"
   */
  "aria-label"?: string;
};

/**
 * A sticky search input pinned above a `ComboboxContent` list. Grafts Base UI's `Input` onto the
 * same search-row chrome `MenuSearch` uses, so the combobox panel matches the dropdown. This _is_
 * the combobox's `Input` — compose it via `ComboboxContent`'s `search` slot instead of
 * `ComboboxInputGroup` / `ComboboxChips`, which already mount an input in the field. Defaults to
 * `aria-label="Search"` (or the `placeholder`, if you changed that) so the combobox stays named.
 */
export function ComboboxSearch({
  placeholder = "Search",
  "aria-label": ariaLabel,
  ...props
}: ComboboxSearchProps) {
  return (
    <ComboboxSearchElement>
      <Icon tint="tertiary" size="md">
        <SearchOutline />
      </Icon>
      <BaseCombobox.Input
        {...props}
        render={<ComboboxSearchInput />}
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
      />
    </ComboboxSearchElement>
  );
}
