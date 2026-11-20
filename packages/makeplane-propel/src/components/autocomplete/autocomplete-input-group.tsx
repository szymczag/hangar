import { Autocomplete as BaseAutocomplete } from "@base-ui/react/autocomplete";
import type * as React from "react";

import {
  AutocompleteInput,
  AutocompleteInputGroup as AutocompleteInputGroupElement,
  AutocompleteInputGroupClear,
  type AutocompleteSize,
} from "../../elements/autocomplete";

export type AutocompleteInputGroupProps = Omit<
  BaseAutocomplete.Input.Props,
  "className" | "style" | "render" | "size"
> & {
  /** Visual size of the input row: height, padding, and icon/text sizing. Required. */
  size: AutocompleteSize;
  /** Input placeholder. */
  placeholder?: string;
  /**
   * Decorative leading element at the inline-start, e.g. `<Icon icon={Search} tint="placeholder"
   * />`.
   */
  icon?: React.ReactNode;
  /**
   * The clear control (e.g. an `IconButton`), grafted onto Base UI's `Clear` behavior. It carries
   * its own — localizable — `aria-label`; the group bakes no label or glyph.
   */
  clear?: React.ReactElement;
  /**
   * The popup-trigger control (e.g. an `IconButton`), grafted onto Base UI's `Trigger` behavior. It
   * carries its own — localizable — `aria-label`; the group bakes no label or glyph.
   */
  trigger?: React.ReactElement;
};

/**
 * The ready-made autocomplete input row: grafts Base UI's `InputGroup` onto the styled bordered
 * frame and Base UI's `Input` onto the styled text field, laying out an optional leading `icon`
 * slot and the consumer-provided `clear`/`trigger` controls. All remaining props pass through to
 * the input (the element that carries the combobox behavior and accessible name).
 */
export function AutocompleteInputGroup({
  size,
  icon,
  clear,
  trigger,
  ...props
}: AutocompleteInputGroupProps) {
  return (
    <BaseAutocomplete.InputGroup render={<AutocompleteInputGroupElement size={size} />}>
      {icon}
      <BaseAutocomplete.Input {...props} render={<AutocompleteInput />} />
      {clear != null ? (
        <AutocompleteInputGroupClear>
          <BaseAutocomplete.Clear render={clear} keepMounted />
        </AutocompleteInputGroupClear>
      ) : null}
      {trigger != null ? <BaseAutocomplete.Trigger render={trigger} /> : null}
    </BaseAutocomplete.InputGroup>
  );
}
